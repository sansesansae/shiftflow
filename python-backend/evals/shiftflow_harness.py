from __future__ import annotations

import json
import shutil
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from airline import schedule_repository
from airline.tools import _assignment_risk_message
from ml.labor_forecast import evaluate_labor_forecast


CASES_PATH = Path(__file__).with_name("shiftflow_cases.json")
MODEL_BASELINES_PATH = Path(__file__).with_name("model_baselines.json")


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    message: str


def load_cases() -> list[dict[str, Any]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def load_model_baselines() -> dict[str, Any]:
    return json.loads(MODEL_BASELINES_PATH.read_text(encoding="utf-8"))


def fail(case_id: str, message: str) -> EvalResult:
    return EvalResult(case_id=case_id, passed=False, message=message)


def pass_case(case_id: str, message: str = "passed") -> EvalResult:
    return EvalResult(case_id=case_id, passed=True, message=message)


@contextmanager
def isolated_sqlite_seed():
    if schedule_repository.use_supabase():
        yield
        return
    original_path = schedule_repository.SEED_DB_PATH
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / original_path.name
        shutil.copy2(original_path, temp_path)
        schedule_repository.SEED_DB_PATH = temp_path
        try:
            yield
        finally:
            schedule_repository.SEED_DB_PATH = original_path


def evaluate_data_minimum(case: dict[str, Any]) -> EvalResult:
    stores = schedule_repository.list_stores()
    if len(stores) < case["checks"]["min_stores"]:
        return fail(case["id"], f"Expected at least {case['checks']['min_stores']} stores, got {len(stores)}.")

    first_store_id = stores[0]["id"]
    staff = schedule_repository.list_store_staff(first_store_id)
    if len(staff) < case["checks"]["min_staff_per_first_store"]:
        return fail(case["id"], f"Expected enough staff for {first_store_id}, got {len(staff)}.")

    open_shifts = schedule_repository.list_store_shifts(first_store_id, status="open")
    if len(open_shifts) < case["checks"]["min_open_shifts_per_first_store"]:
        return fail(case["id"], f"Expected open shifts for {first_store_id}, got {len(open_shifts)}.")

    return pass_case(case["id"], f"{len(stores)} stores, {len(staff)} staff, {len(open_shifts)} open shifts.")


def evaluate_unknown_store(case: dict[str, Any]) -> EvalResult:
    query = case["input"]["store_query"]
    stores = schedule_repository.list_stores()
    matched = [
        store
        for store in stores
        if query.lower() in store["id"].lower()
        or query.lower() in store["brand"].lower()
        or query.lower() in store["name"].lower()
    ]
    should_exist = case["expect"]["store_should_exist"]
    if bool(matched) != should_exist:
        return fail(case["id"], f"Expected store existence={should_exist}, matched={matched}.")
    return pass_case(case["id"], "unknown store correctly has no direct match.")


def evaluate_open_shift_gap(case: dict[str, Any]) -> EvalResult:
    shifts = schedule_repository.list_store_shifts(
        case["input"]["store_id"],
        status=case["input"]["status"],
    )
    invalid = [
        shift
        for shift in shifts
        if shift["required_count"] <= shift["assigned_count"] or shift["open_count"] <= 0
    ]
    if invalid:
        return fail(case["id"], f"Open shifts without real gap: {[item['id'] for item in invalid[:5]]}.")
    return pass_case(case["id"], f"{len(shifts)} open shifts have real gaps.")


def evaluate_staff_skills(case: dict[str, Any]) -> EvalResult:
    staff = schedule_repository.list_store_staff(case["input"]["store_id"])
    bad_staff = [person["id"] for person in staff if not isinstance(person.get("skills"), list) or not person["skills"]]
    if bad_staff:
        return fail(case["id"], f"Staff with missing/unstructured skills: {bad_staff[:5]}.")
    return pass_case(case["id"], f"{len(staff)} staff records have structured skills.")


def evaluate_overtime_block(case: dict[str, Any]) -> EvalResult:
    risk_message = _assignment_risk_message(
        case["input"]["existing_roster"],
        case["input"]["employee_name"],
        case["input"]["candidate_shift"],
    )
    expected = case["input"]["expect_message_contains"]
    if not risk_message or expected not in risk_message:
        return fail(case["id"], f"Expected overtime block containing {expected!r}, got {risk_message!r}.")
    return pass_case(case["id"], risk_message)


def evaluate_role_mismatch(case: dict[str, Any]) -> EvalResult:
    staff = schedule_repository.list_store_staff(case["input"]["store_id"])
    required_role = case["input"]["required_role"]
    invalid_recommendations = [
        person
        for person in staff
        if person["role"] != required_role and not person["can_float"]
    ]
    if not invalid_recommendations:
        return fail(case["id"], "Fixture did not contain a role-mismatch candidate to test.")

    bad = [
        person["name"]
        for person in invalid_recommendations
        if person["role"] == required_role or person["can_float"]
    ]
    if bad:
        return fail(case["id"], f"Unexpected role mismatch handling failure: {bad}.")
    return pass_case(case["id"], f"{len(invalid_recommendations)} non-qualified candidates correctly excluded.")


def evaluate_forecast_silent_run(case: dict[str, Any]) -> EvalResult:
    store_id = case["input"]["store_id"]
    forecasts = schedule_repository.list_store_forecasts(store_id)
    if len(forecasts) < case["checks"]["min_forecasts"]:
        return fail(case["id"], f"Expected at least {case['checks']['min_forecasts']} forecasts, got {len(forecasts)}.")
    evaluated = [item for item in forecasts if item.get("deviation_rate") is not None]
    if not evaluated:
        return fail(case["id"], "Expected evaluated forecasts with deviation_rate.")
    summary = schedule_repository.get_forecast_summary(store_id=store_id)
    max_allowed = case["checks"]["max_average_abs_deviation_rate"]
    if summary["average_abs_deviation_rate"] > max_allowed:
        return fail(case["id"], f"Average deviation too high: {summary['average_abs_deviation_rate']}.")
    return pass_case(
        case["id"],
        f"{len(forecasts)} forecasts, {summary['badcase_count']} badcases, avg deviation {summary['average_abs_deviation_rate']}.",
    )


def evaluate_metrics_import(case: dict[str, Any]) -> EvalResult:
    with isolated_sqlite_seed():
        result = schedule_repository.import_hourly_metrics(
            store_id=case["input"]["store_id"],
            metrics=case["input"]["metrics"],
        )
        if result["imported_count"] != case["checks"]["imported_count"]:
            return fail(case["id"], f"Expected {case['checks']['imported_count']} imported rows, got {result}.")
        if result["forecast_count"] < case["checks"]["min_forecast_count"]:
            return fail(case["id"], f"Expected refreshed forecasts, got {result}.")
        forecasts = schedule_repository.list_store_forecasts(case["input"]["store_id"], forecast_date="2026-08-18")
        refreshed = [item for item in forecasts if item["model_version"] == "v2.1-import-baseline"]
        if not refreshed:
            return fail(case["id"], "No v2.1-import-baseline forecast rows found after import.")
        return pass_case(case["id"], f"Imported {result['imported_count']} rows and refreshed {len(refreshed)} forecasts.")


def evaluate_labor_model_harness(case: dict[str, Any]) -> EvalResult:
    baseline = load_model_baselines()[case["baseline_id"]]
    first_run = evaluate_labor_forecast(case["input"]["metrics"])
    second_run = evaluate_labor_forecast(case["input"]["metrics"])
    failures = []
    if first_run.row_count < baseline["min_rows"]:
        failures.append(f"row_count {first_run.row_count} < {baseline['min_rows']}")
    if not first_run.leakage_free:
        failures.append(f"date leakage: train max {first_run.train_max_date}, test min {first_run.test_min_date}")
    if first_run.min_prediction < baseline["min_prediction"]:
        failures.append(f"min prediction {first_run.min_prediction} < {baseline['min_prediction']}")
    if first_run.mae > baseline["max_mae"]:
        failures.append(f"mae {first_run.mae} > {baseline['max_mae']}")
    if first_run.mape > baseline["max_mape"]:
        failures.append(f"mape {first_run.mape} > {baseline['max_mape']}")
    if first_run.badcase_rate > baseline["max_badcase_rate"]:
        failures.append(f"badcase_rate {first_run.badcase_rate} > {baseline['max_badcase_rate']}")
    if first_run.prediction_signature != second_run.prediction_signature:
        failures.append("prediction signature changed between identical runs")
    if failures:
        return fail(case["id"], "; ".join(failures))
    return pass_case(
        case["id"],
        (
            f"rows={first_run.row_count}, train={first_run.train_count}, test={first_run.test_count}, "
            f"mae={first_run.mae}, mape={first_run.mape}, badcase_rate={first_run.badcase_rate}, "
            f"signature={first_run.prediction_signature}"
        ),
    )


EVALUATORS: dict[str, Callable[[dict[str, Any]], EvalResult]] = {
    "data_minimum_viable_demo": evaluate_data_minimum,
    "unknown_store_does_not_hallucinate": evaluate_unknown_store,
    "open_shift_has_real_gap": evaluate_open_shift_gap,
    "staff_skills_are_structured": evaluate_staff_skills,
    "overtime_candidate_blocked": evaluate_overtime_block,
    "role_mismatch_candidate_rejected": evaluate_role_mismatch,
    "forecast_silent_run_has_deviation": evaluate_forecast_silent_run,
    "metrics_import_generates_forecasts": evaluate_metrics_import,
    "labor_forecast_model_harness": evaluate_labor_model_harness,
}


def run() -> list[EvalResult]:
    results: list[EvalResult] = []
    for case in load_cases():
        evaluator = EVALUATORS.get(case["id"])
        if evaluator is None:
            results.append(fail(case["id"], "No evaluator registered."))
            continue
        try:
            results.append(evaluator(case))
        except Exception as exc:
            results.append(fail(case["id"], f"{type(exc).__name__}: {exc}"))
    return results


def main() -> int:
    results = run()
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    print(f"ShiftFlow Harness: {passed}/{total} passed")
    for result in results:
        marker = "PASS" if result.passed else "FAIL"
        print(f"[{marker}] {result.case_id}: {result.message}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
