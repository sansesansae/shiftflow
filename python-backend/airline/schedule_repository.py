from __future__ import annotations

import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    from supabase import Client, create_client
except ModuleNotFoundError:
    Client = Any
    create_client = None


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SEED_DB_PATH = DATA_DIR / "shiftflow_seed.sqlite"


def use_supabase() -> bool:
    return bool(create_client and os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


@lru_cache
def supabase_client() -> Client:
    if create_client is None:
        raise RuntimeError("Supabase is configured but the supabase package is not installed.")
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(SEED_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def decode_json_list(value: str | list[str] | None) -> list[str]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def normalize_time(value: str | None) -> str:
    return value[:5] if value else ""


def normalize_store(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("external_id") or row["id"],
        "brand": row["brand"],
        "name": row["name"],
        "city": row["city"],
        "district": row["district"],
        "address": row["address"],
        "business_type": row["business_type"],
        "opening_time": normalize_time(row.get("opening_time")),
        "closing_time": normalize_time(row.get("closing_time")),
        "status": row["status"],
    }


def normalize_employee(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("external_id") or row["id"],
        "store_id": (row.get("stores") or {}).get("external_id") or row.get("store_id"),
        "name": row["name"],
        "role": row["role"],
        "skills": decode_json_list(row.get("skills")),
        "weekly_hour_limit": row["weekly_hour_limit"],
        "scheduled_hours": int(row["scheduled_hours"]),
        "can_close": bool(row["can_close"]),
        "can_float": bool(row["can_float"]),
        "phone": row.get("phone") or "",
        "status": row["status"],
    }


def normalize_shift(row: dict[str, Any]) -> dict[str, Any]:
    store = row.get("stores") or {}
    template = row.get("shift_templates") or {}
    required_count = row["required_count"]
    assigned_count = row["assigned_count"]
    return {
        "id": row.get("external_id") or row["id"],
        "store_id": store.get("external_id") or row.get("store_id"),
        "store_name": store.get("name", ""),
        "template_id": template.get("external_id") or row.get("template_id"),
        "template_name": template.get("name", ""),
        "shift_date": row["shift_date"],
        "start_time": normalize_time(row.get("start_time")),
        "end_time": normalize_time(row.get("end_time")),
        "required_role": row["required_role"],
        "required_count": required_count,
        "assigned_count": assigned_count,
        "open_count": max(required_count - assigned_count, 0),
        "status": row["status"],
        "note": row.get("note"),
    }


def normalize_forecast(row: dict[str, Any]) -> dict[str, Any]:
    store = row.get("stores") or {}
    evaluation = row.get("forecast_evaluations")
    if isinstance(evaluation, list):
        evaluation = evaluation[0] if evaluation else {}
    evaluation = evaluation or {}
    predicted = float(row["predicted_labor_hours"])
    actual = evaluation.get("actual_labor_hours")
    absolute_error = evaluation.get("absolute_error")
    deviation_rate = evaluation.get("deviation_rate")
    return {
        "id": row.get("external_id") or row["id"],
        "store_id": store.get("external_id") or row.get("store_id"),
        "store_name": store.get("name", ""),
        "forecast_date": row["forecast_date"],
        "hour": int(row["hour"]),
        "role": row["role"],
        "model_name": row["model_name"],
        "model_version": row["model_version"],
        "predicted_labor_hours": predicted,
        "baseline_labor_hours": float(row["baseline_labor_hours"]),
        "actual_labor_hours": float(actual) if actual is not None else None,
        "deviation_rate": float(deviation_rate) if deviation_rate is not None else None,
        "absolute_error": float(absolute_error) if absolute_error is not None else None,
        "status": evaluation.get("status") or "pending",
        "confidence": row["confidence"],
        "features": row.get("features") or {},
        "notes": evaluation.get("notes"),
    }


def normalize_hourly_metric(row: dict[str, Any]) -> dict[str, Any]:
    store = row.get("stores") or {}
    return {
        "id": row.get("external_id") or row["id"],
        "store_id": store.get("external_id") or row.get("store_id"),
        "metric_date": row["metric_date"],
        "hour": int(row["hour"]),
        "role": row["role"],
        "order_count": int(row["order_count"]),
        "sales_amount": float(row["sales_amount"]),
        "weather": row["weather"],
        "temperature": float(row["temperature"]) if row.get("temperature") is not None else None,
        "is_weekend": bool(row["is_weekend"]),
        "is_holiday": bool(row["is_holiday"]),
        "promotion_flag": bool(row["promotion_flag"]),
        "actual_labor_hours": float(row["actual_labor_hours"]),
    }


def _external_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _shift_hours(shift: dict[str, Any]) -> int:
    start_hour = int(str(shift["start_time"])[:2])
    end_hour = int(str(shift["end_time"])[:2])
    if end_hour <= start_hour:
        end_hour += 24
    return max(end_hour - start_hour, 1)


def _time_window(value: dict[str, Any]) -> tuple[float, float]:
    start_text = str(value["start_time"])[:5]
    end_text = str(value["end_time"])[:5]
    start_hour, start_minute = [int(part) for part in start_text.split(":")]
    end_hour, end_minute = [int(part) for part in end_text.split(":")]
    start = start_hour + start_minute / 60
    end = end_hour + end_minute / 60
    if end <= start:
        end += 24
    return start, end


def _time_overlaps(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_start, left_end = _time_window(left)
    right_start, right_end = _time_window(right)
    return left_start < right_end and right_start < left_end


def _is_closing_shift(shift: dict[str, Any]) -> bool:
    template_name = str(shift.get("template_name") or "")
    _, end = _time_window(shift)
    return "闭店" in template_name or end >= 22 or end > 24


def _role_matches(employee: dict[str, Any], shift: dict[str, Any]) -> bool:
    required_role = str(shift.get("required_role") or "").strip()
    if not required_role:
        return True
    role = str(employee.get("role") or "")
    skills = decode_json_list(employee.get("skills"))
    return required_role in role or required_role in skills


def evaluate_assignment_risks(
    store_id: str,
    shift: dict[str, Any],
    employee: dict[str, Any],
) -> list[str]:
    risk_flags: list[str] = []
    if not _role_matches(employee, shift):
        risk_flags.append(
            f"岗位不匹配：该班次需要 {shift['required_role']}，但 {employee['name']} 是 {employee['role']}。"
        )
    if _is_closing_shift(shift) and not bool(employee.get("can_close")):
        risk_flags.append(f"闭店能力不足：{employee['name']} 未标记为可闭店。")

    projected_hours = float(employee["scheduled_hours"]) + _shift_hours(shift)
    if projected_hours > float(employee["weekly_hour_limit"]):
        risk_flags.append(
            f"工时超限：补位后本周约 {projected_hours:.0f}h，超过 {employee['weekly_hour_limit']}h 上限。"
        )

    assignments = list_employee_assignments(employee_name=employee["name"], shift_date=shift["shift_date"])
    for assignment in assignments:
        if assignment.get("shift_id") == shift["id"]:
            risk_flags.append(f"重复排班：{employee['name']} 已在这个班次中。")
            continue
        if assignment.get("shift_date") == shift["shift_date"] and _time_overlaps(assignment, shift):
            risk_flags.append(
                f"时间冲突：{employee['name']} 当天已有 {assignment['template_name']} "
                f"{assignment['start_time']}-{assignment['end_time']}。"
            )

    if employee.get("store_id") != store_id:
        risk_flags.append("门店不匹配：员工不属于当前门店。")

    return risk_flags


def verify_supabase_user(access_token: str) -> dict[str, Any]:
    if not use_supabase():
        raise ValueError("Supabase auth is not available.")
    response = supabase_client().auth.get_user(access_token)
    user = getattr(response, "user", None)
    if not user:
        raise ValueError("登录已失效，请重新登录。")
    return {
        "id": str(user.id),
        "email": getattr(user, "email", None),
    }


def user_can_write_store(user_id: str, store_id: str) -> bool:
    if not use_supabase():
        return True
    client = supabase_client()
    profile_rows = (
        client.table("user_profiles")
        .select("id, role, status")
        .eq("id", user_id)
        .eq("status", "active")
        .limit(1)
        .execute()
        .data
    )
    if not profile_rows:
        return False
    if profile_rows[0]["role"] == "ops_admin":
        return True

    permission_rows = (
        client.table("user_store_permissions")
        .select("permission, scope, stores!left(external_id)")
        .eq("user_id", user_id)
        .eq("status", "active")
        .in_("permission", ["write", "approve", "admin"])
        .execute()
        .data
    )
    for row in permission_rows:
        if row["scope"] == "all":
            return True
        store = row.get("stores") or {}
        if store.get("external_id") == store_id:
            return True
    return False


def create_audit_log(
    action: str,
    user_id: str | None,
    store_id: str,
    shift_id: str | None = None,
    employee_id: str | None = None,
    payload: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    source: str = "web",
) -> None:
    if not use_supabase():
        return
    client = supabase_client()
    store_rows = (
        client.table("stores")
        .select("id")
        .eq("external_id", store_id)
        .limit(1)
        .execute()
        .data
    )
    shift_rows = []
    if shift_id:
        shift_rows = (
            client.table("shifts")
            .select("id")
            .eq("external_id", shift_id)
            .limit(1)
            .execute()
            .data
        )
    employee_rows = []
    if employee_id:
        employee_rows = (
            client.table("employees")
            .select("id")
            .eq("external_id", employee_id)
            .limit(1)
            .execute()
            .data
        )
    client.table("audit_logs").insert(
        {
            "external_id": _external_id("audit"),
            "user_id": user_id,
            "action": action,
            "store_id": store_rows[0]["id"] if store_rows else None,
            "shift_id": shift_rows[0]["id"] if shift_rows else None,
            "employee_id": employee_rows[0]["id"] if employee_rows else None,
            "payload": payload or {},
            "result": result or {},
            "source": source,
        }
    ).execute()


def find_store_id(text: str | None = None) -> str:
    if use_supabase():
        rows = list_stores()
        if text:
            lowered = text.lower()
            for row in rows:
                if row["id"].lower() in lowered or row["brand"].lower() in lowered or row["name"].lower() in lowered:
                    return row["id"]
        return rows[0]["id"] if rows else ""

    with connect() as conn:
        if text:
            lowered = text.lower()
            rows = conn.execute(
                "SELECT id, brand, name FROM stores WHERE status = 'active'"
            ).fetchall()
            for row in rows:
                if row["id"].lower() in lowered or row["brand"].lower() in lowered or row["name"].lower() in lowered:
                    return row["id"]
        row = conn.execute(
            "SELECT id FROM stores WHERE status = 'active' ORDER BY city, brand, name LIMIT 1"
        ).fetchone()
    return row["id"] if row else ""


def list_stores() -> list[dict[str, Any]]:
    if use_supabase():
        response = (
            supabase_client()
            .table("stores")
            .select("id, external_id, brand, name, city, district, address, business_type, opening_time, closing_time, status")
            .eq("status", "active")
            .order("city")
            .order("brand")
            .order("name")
            .execute()
        )
        return [normalize_store(row) for row in response.data]

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, brand, name, city, district, address, business_type,
                   opening_time, closing_time, status
            FROM stores
            WHERE status = 'active'
            ORDER BY city, brand, name
            """
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def list_store_staff(store_id: str) -> list[dict[str, Any]]:
    if use_supabase():
        response = (
            supabase_client()
            .table("employees")
            .select(
                "id, external_id, name, role, skills, weekly_hour_limit, scheduled_hours, "
                "can_close, can_float, phone, status, stores!inner(external_id)"
            )
            .eq("stores.external_id", store_id)
            .eq("status", "active")
            .order("role")
            .order("name")
            .execute()
        )
        return [normalize_employee(row) for row in response.data]

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, store_id, name, role, skills, weekly_hour_limit,
                   scheduled_hours, can_close, can_float, phone, status
            FROM employees
            WHERE store_id = ? AND status = 'active'
            ORDER BY role, name
            """,
            (store_id,),
        ).fetchall()
    staff = []
    for row in rows:
        item = row_to_dict(row)
        item["skills"] = decode_json_list(item.get("skills"))
        item["can_close"] = bool(item.get("can_close"))
        item["can_float"] = bool(item.get("can_float"))
        staff.append(item)
    return staff


def list_store_shifts(
    store_id: str,
    shift_date: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    if use_supabase():
        query = (
            supabase_client()
            .table("shifts")
            .select(
                "id, external_id, shift_date, start_time, end_time, required_role, required_count, "
                "assigned_count, status, note, stores!inner(external_id, name), "
                "shift_templates(external_id, name)"
            )
            .eq("stores.external_id", store_id)
        )
        if shift_date:
            query = query.eq("shift_date", shift_date)
        if status:
            query = query.eq("status", status)
        response = query.order("shift_date").order("start_time").order("required_role").execute()
        return [normalize_shift(row) for row in response.data]

    clauses = ["sh.store_id = ?"]
    params: list[Any] = [store_id]
    if shift_date:
        clauses.append("sh.shift_date = ?")
        params.append(shift_date)
    if status:
        clauses.append("sh.status = ?")
        params.append(status)

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT sh.id, sh.store_id, st.name AS store_name, sh.template_id,
                   tpl.name AS template_name, sh.shift_date, sh.start_time,
                   sh.end_time, sh.required_role, sh.required_count,
                   sh.assigned_count, sh.status, sh.note
            FROM shifts sh
            JOIN stores st ON st.id = sh.store_id
            JOIN shift_templates tpl ON tpl.id = sh.template_id
            WHERE {' AND '.join(clauses)}
            ORDER BY sh.shift_date, sh.start_time, sh.required_role
            """,
            params,
        ).fetchall()

    shifts = []
    for row in rows:
        item = row_to_dict(row)
        item["open_count"] = max(item["required_count"] - item["assigned_count"], 0)
        shifts.append(item)
    return shifts


def _forecast_from_shift(store: dict[str, Any], shift: dict[str, Any], index: int) -> dict[str, Any]:
    hour = int(str(shift["start_time"])[:2])
    is_peak = "高峰" in str(shift["template_name"])
    is_closing = "闭店" in str(shift["template_name"])
    baseline = float(max(shift["required_count"], 1))
    predicted = baseline + (0.5 if is_peak else 0.0) + (0.25 if is_closing else 0.0)
    actual = float(max(shift["assigned_count"], 0)) + (0.75 if shift["open_count"] > 0 else 0.0)
    deviation_rate = (actual - predicted) / predicted if predicted else 0.0
    absolute_error = abs(actual - predicted)
    status = "badcase" if abs(deviation_rate) >= 0.18 else "evaluated"
    return {
        "id": f"forecast_{shift['id']}",
        "store_id": store["id"],
        "store_name": store["name"],
        "forecast_date": shift["shift_date"],
        "hour": hour,
        "role": shift["required_role"],
        "model_name": "same-weekday-hour-baseline",
        "model_version": "v2-baseline-2026-08",
        "predicted_labor_hours": round(predicted, 2),
        "baseline_labor_hours": round(baseline, 2),
        "actual_labor_hours": round(actual, 2),
        "deviation_rate": round(deviation_rate, 4),
        "absolute_error": round(absolute_error, 2),
        "status": status,
        "confidence": "high" if index % 3 else "medium",
        "features": {
            "shift_template": shift["template_name"],
            "open_count": shift["open_count"],
            "source": "schedule-derived-demo",
        },
        "notes": "静默试跑：由当前班次需求和实际到岗情况生成的演示预测。",
    }


def _fallback_forecasts(store_id: str, forecast_date: str | None = None) -> list[dict[str, Any]]:
    store = next((item for item in list_stores() if item["id"] == store_id), None)
    if not store:
        return []
    shifts = list_store_shifts(store_id, shift_date=forecast_date)
    return [_forecast_from_shift(store, shift, index) for index, shift in enumerate(shifts[:24])]


def list_store_forecasts(
    store_id: str,
    forecast_date: str | None = None,
) -> list[dict[str, Any]]:
    if use_supabase():
        client = supabase_client()
        query = (
            client.table("labor_forecasts")
            .select(
                "id, external_id, forecast_date, hour, role, model_name, model_version, "
                "predicted_labor_hours, baseline_labor_hours, confidence, features, "
                "stores!inner(external_id, name), "
                "forecast_evaluations(actual_labor_hours, deviation_rate, absolute_error, status, notes)"
            )
            .eq("stores.external_id", store_id)
        )
        if forecast_date:
            query = query.eq("forecast_date", forecast_date)
        response = query.order("forecast_date").order("hour").order("role").execute()
        rows = [normalize_forecast(row) for row in response.data]
        return rows if rows else _fallback_forecasts(store_id, forecast_date)

    with connect() as conn:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'labor_forecasts'"
        ).fetchone()
        if not table_exists:
            return _fallback_forecasts(store_id, forecast_date)
        clauses = ["st.id = ?"]
        params: list[Any] = [store_id]
        if forecast_date:
            clauses.append("lf.forecast_date = ?")
            params.append(forecast_date)
        rows = conn.execute(
            f"""
            SELECT lf.id, lf.store_id, st.name AS store_name, lf.forecast_date, lf.hour,
                   lf.role, lf.model_name, lf.model_version, lf.predicted_labor_hours,
                   lf.baseline_labor_hours, lf.confidence, lf.features,
                   fe.actual_labor_hours, fe.deviation_rate, fe.absolute_error,
                   fe.status, fe.notes
            FROM labor_forecasts lf
            JOIN stores st ON st.id = lf.store_id
            LEFT JOIN forecast_evaluations fe ON fe.forecast_id = lf.id
            WHERE {' AND '.join(clauses)}
            ORDER BY lf.forecast_date, lf.hour, lf.role
            """,
            params,
        ).fetchall()
    forecasts = []
    for row in rows:
        item = row_to_dict(row)
        item["features"] = json.loads(item["features"]) if item.get("features") else {}
        forecasts.append(item)
    return forecasts if forecasts else _fallback_forecasts(store_id, forecast_date)


def _baseline_adjustment(metric: dict[str, Any]) -> float:
    factor = 1.0
    if metric.get("is_weekend"):
        factor += 0.08
    if metric.get("is_holiday"):
        factor += 0.12
    if metric.get("promotion_flag"):
        factor += 0.15
    if str(metric.get("weather") or "").lower() in {"rain", "雨", "小雨", "大雨"}:
        factor += 0.05
    return factor


def _forecast_status(deviation_rate: float) -> str:
    return "badcase" if abs(deviation_rate) >= 0.18 else "evaluated"


def _forecast_confidence(sample_count: int) -> str:
    if sample_count >= 8:
        return "high"
    if sample_count >= 3:
        return "medium"
    return "low"


def _forecast_rows_from_metrics(
    store_id: str,
    metrics: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    buckets: dict[tuple[int, str], list[float]] = defaultdict(list)
    for metric in metrics:
        buckets[(int(metric["hour"]), str(metric["role"]))].append(float(metric["actual_labor_hours"]))

    forecasts = []
    evaluations = []
    for metric in metrics:
        key = (int(metric["hour"]), str(metric["role"]))
        samples = buckets[key]
        baseline = sum(samples) / len(samples)
        predicted = max(baseline * _baseline_adjustment(metric), 0)
        actual = float(metric["actual_labor_hours"])
        deviation_rate = (actual - predicted) / predicted if predicted else 0
        absolute_error = abs(actual - predicted)
        forecast_id = (
            f"forecast_import_{store_id}_{metric['metric_date']}_{metric['hour']}_{metric['role']}"
            .replace(" ", "_")
            .replace(":", "")
        )
        forecasts.append(
            {
                "external_id": forecast_id,
                "forecast_date": metric["metric_date"],
                "hour": int(metric["hour"]),
                "role": metric["role"],
                "model_name": "same-hour-role-import-baseline",
                "model_version": "v2.1-import-baseline",
                "predicted_labor_hours": round(predicted, 2),
                "baseline_labor_hours": round(baseline, 2),
                "confidence": _forecast_confidence(len(samples)),
                "features": {
                    "order_count": metric["order_count"],
                    "sales_amount": metric["sales_amount"],
                    "weather": metric["weather"],
                    "temperature": metric.get("temperature"),
                    "is_weekend": metric["is_weekend"],
                    "is_holiday": metric["is_holiday"],
                    "promotion_flag": metric["promotion_flag"],
                    "sample_count": len(samples),
                    "source": "csv_import",
                },
            }
        )
        evaluations.append(
            {
                "forecast_external_id": forecast_id,
                "external_id": f"eval_{forecast_id}",
                "actual_labor_hours": round(actual, 2),
                "deviation_rate": round(deviation_rate, 4),
                "absolute_error": round(absolute_error, 2),
                "status": _forecast_status(deviation_rate),
                "notes": "CSV 导入后自动生成的静默试跑评估。",
            }
        )
    return forecasts, evaluations


def _list_hourly_metrics_for_store(store_id: str) -> list[dict[str, Any]]:
    if use_supabase():
        response = (
            supabase_client()
            .table("hourly_store_metrics")
            .select(
                "id, external_id, metric_date, hour, role, order_count, sales_amount, weather, "
                "temperature, is_weekend, is_holiday, promotion_flag, actual_labor_hours, "
                "stores!inner(external_id)"
            )
            .eq("stores.external_id", store_id)
            .execute()
        )
        return [normalize_hourly_metric(row) for row in response.data]

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, store_id, metric_date, hour, role, order_count, sales_amount,
                   weather, temperature, is_weekend, is_holiday, promotion_flag,
                   actual_labor_hours
            FROM hourly_store_metrics
            WHERE store_id = ?
            ORDER BY metric_date, hour, role
            """,
            (store_id,),
        ).fetchall()
    metrics = []
    for row in rows:
        item = row_to_dict(row)
        item["is_weekend"] = bool(item["is_weekend"])
        item["is_holiday"] = bool(item["is_holiday"])
        item["promotion_flag"] = bool(item["promotion_flag"])
        metrics.append(item)
    return metrics


def import_hourly_metrics(
    store_id: str,
    metrics: list[dict[str, Any]],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    if not metrics:
        return {"imported_count": 0, "forecast_count": 0, "badcase_count": 0}

    now = datetime.utcnow().isoformat()
    if use_supabase():
        client = supabase_client()
        store_rows = (
            client.table("stores")
            .select("id, external_id")
            .eq("external_id", store_id)
            .limit(1)
            .execute()
            .data
        )
        if not store_rows:
            raise ValueError("门店不存在。")
        store_uuid = store_rows[0]["id"]
        metric_rows = []
        for metric in metrics:
            metric_rows.append(
                {
                    "external_id": f"metric_import_{store_id}_{metric['metric_date']}_{metric['hour']}_{metric['role']}".replace(" ", "_"),
                    "store_id": store_uuid,
                    "metric_date": metric["metric_date"],
                    "hour": int(metric["hour"]),
                    "role": metric["role"],
                    "order_count": int(metric["order_count"]),
                    "sales_amount": float(metric["sales_amount"]),
                    "weather": metric["weather"],
                    "temperature": metric.get("temperature"),
                    "is_weekend": bool(metric["is_weekend"]),
                    "is_holiday": bool(metric["is_holiday"]),
                    "promotion_flag": bool(metric["promotion_flag"]),
                    "actual_labor_hours": float(metric["actual_labor_hours"]),
                }
            )
        client.table("hourly_store_metrics").upsert(
            metric_rows,
            on_conflict="store_id,metric_date,hour,role",
        ).execute()

        all_metrics = _list_hourly_metrics_for_store(store_id)
        imported_dates = {metric["metric_date"] for metric in metrics}
        forecast_source = [metric for metric in all_metrics if metric["metric_date"] in imported_dates]
        forecasts, evaluations = _forecast_rows_from_metrics(store_id, forecast_source)
        forecast_rows = [{**row, "store_id": store_uuid} for row in forecasts]
        if forecast_rows:
            client.table("labor_forecasts").upsert(
                forecast_rows,
                on_conflict="store_id,forecast_date,hour,role,model_version",
            ).execute()
            forecast_lookup = (
                client.table("labor_forecasts")
                .select("id, external_id")
                .eq("store_id", store_uuid)
                .eq("model_version", "v2.1-import-baseline")
                .in_("forecast_date", sorted(imported_dates))
                .execute()
                .data
            )
            id_by_external = {row["external_id"]: row["id"] for row in forecast_lookup}
            evaluation_rows = [
                {
                    "external_id": item["external_id"],
                    "forecast_id": id_by_external[item["forecast_external_id"]],
                    "actual_labor_hours": item["actual_labor_hours"],
                    "deviation_rate": item["deviation_rate"],
                    "absolute_error": item["absolute_error"],
                    "status": item["status"],
                    "notes": item["notes"],
                }
                for item in evaluations
                if item["forecast_external_id"] in id_by_external
            ]
            if evaluation_rows:
                client.table("forecast_evaluations").upsert(
                    evaluation_rows,
                    on_conflict="forecast_id",
                ).execute()
        badcase_count = sum(1 for item in evaluations if item["status"] == "badcase")
        create_audit_log(
            action="import_hourly_metrics",
            user_id=actor_user_id,
            store_id=store_id,
            payload={"imported_count": len(metrics), "source": "csv"},
            result={"forecast_count": len(forecasts), "badcase_count": badcase_count},
        )
        return {
            "imported_count": len(metrics),
            "forecast_count": len(forecasts),
            "badcase_count": badcase_count,
        }

    with connect() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript((DATA_DIR / "schema.sql").read_text(encoding="utf-8"))
        for metric in metrics:
            conn.execute(
                """
                DELETE FROM hourly_store_metrics
                WHERE store_id = ? AND metric_date = ? AND hour = ? AND role = ?
                """,
                (store_id, metric["metric_date"], int(metric["hour"]), metric["role"]),
            )
            conn.execute(
                """
                INSERT INTO hourly_store_metrics (
                  id, store_id, metric_date, hour, role, order_count, sales_amount,
                  weather, temperature, is_weekend, is_holiday, promotion_flag,
                  actual_labor_hours, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"metric_import_{store_id}_{metric['metric_date']}_{metric['hour']}_{metric['role']}".replace(" ", "_"),
                    store_id,
                    metric["metric_date"],
                    int(metric["hour"]),
                    metric["role"],
                    int(metric["order_count"]),
                    float(metric["sales_amount"]),
                    metric["weather"],
                    metric.get("temperature"),
                    int(bool(metric["is_weekend"])),
                    int(bool(metric["is_holiday"])),
                    int(bool(metric["promotion_flag"])),
                    float(metric["actual_labor_hours"]),
                    now,
                ),
            )
        conn.commit()

        all_metrics = _list_hourly_metrics_for_store(store_id)
        imported_dates = {metric["metric_date"] for metric in metrics}
        forecast_source = [metric for metric in all_metrics if metric["metric_date"] in imported_dates]
        forecasts, evaluations = _forecast_rows_from_metrics(store_id, forecast_source)
        for forecast in forecasts:
            conn.execute("DELETE FROM forecast_evaluations WHERE forecast_id = ?", (forecast["external_id"],))
            conn.execute("DELETE FROM labor_forecasts WHERE id = ?", (forecast["external_id"],))
            conn.execute(
                """
                INSERT INTO labor_forecasts (
                  id, store_id, forecast_date, hour, role, model_name, model_version,
                  predicted_labor_hours, baseline_labor_hours, confidence, features, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    forecast["external_id"],
                    store_id,
                    forecast["forecast_date"],
                    forecast["hour"],
                    forecast["role"],
                    forecast["model_name"],
                    forecast["model_version"],
                    forecast["predicted_labor_hours"],
                    forecast["baseline_labor_hours"],
                    forecast["confidence"],
                    json.dumps(forecast["features"], ensure_ascii=False),
                    now,
                ),
            )
        for evaluation in evaluations:
            conn.execute(
                "DELETE FROM forecast_evaluations WHERE forecast_id = ?",
                (evaluation["forecast_external_id"],),
            )
            conn.execute(
                """
                INSERT INTO forecast_evaluations (
                  id, forecast_id, actual_labor_hours, deviation_rate,
                  absolute_error, status, notes, evaluated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evaluation["external_id"],
                    evaluation["forecast_external_id"],
                    evaluation["actual_labor_hours"],
                    evaluation["deviation_rate"],
                    evaluation["absolute_error"],
                    evaluation["status"],
                    evaluation["notes"],
                    now,
                ),
            )
        conn.commit()
    return {
        "imported_count": len(metrics),
        "forecast_count": len(forecasts),
        "badcase_count": sum(1 for item in evaluations if item["status"] == "badcase"),
    }


def get_forecast_summary(store_id: str | None = None) -> dict[str, Any]:
    stores = [store for store in list_stores() if store_id in {None, store["id"]}]
    forecasts = [
        forecast
        for store in stores
        for forecast in list_store_forecasts(store["id"])
    ]
    evaluated = [item for item in forecasts if item.get("actual_labor_hours") is not None]
    total_predicted = sum(float(item["predicted_labor_hours"]) for item in forecasts)
    total_actual = sum(float(item.get("actual_labor_hours") or 0) for item in evaluated)
    avg_abs_deviation = (
        sum(abs(float(item.get("deviation_rate") or 0)) for item in evaluated) / len(evaluated)
        if evaluated
        else 0.0
    )
    badcase_count = sum(1 for item in evaluated if item.get("status") == "badcase")
    next_focus = sorted(
        evaluated,
        key=lambda item: abs(float(item.get("deviation_rate") or 0)),
        reverse=True,
    )[:3]
    return {
        "store_count": len(stores),
        "forecast_count": len(forecasts),
        "evaluated_count": len(evaluated),
        "badcase_count": badcase_count,
        "total_predicted_labor_hours": round(total_predicted, 2),
        "total_actual_labor_hours": round(total_actual, 2),
        "average_abs_deviation_rate": round(avg_abs_deviation, 4),
        "model_name": "same-weekday-hour-baseline",
        "model_version": "v2-baseline-2026-08",
        "next_focus": next_focus,
    }


def list_employee_assignments(
    employee_name: str | None = None,
    shift_date: str | None = None,
) -> list[dict[str, Any]]:
    if use_supabase():
        query = (
            supabase_client()
            .table("shift_assignments")
            .select(
                "employees!inner(name, role, scheduled_hours), "
                "shifts!inner(external_id, shift_date, start_time, end_time, required_role, "
                "stores!inner(name), shift_templates(name))"
            )
        )
        if employee_name:
            query = query.ilike("employees.name", f"%{employee_name}%")
        if shift_date:
            query = query.eq("shifts.shift_date", shift_date)
        response = query.limit(20).execute()
        rows = []
        for row in response.data:
            employee = row["employees"]
            shift = row["shifts"]
            rows.append(
                {
                    "employee_name": employee["name"],
                    "role": employee["role"],
                    "scheduled_hours": int(employee["scheduled_hours"]),
                    "store_name": shift["stores"]["name"],
                    "shift_id": shift["external_id"],
                    "shift_date": shift["shift_date"],
                    "start_time": normalize_time(shift.get("start_time")),
                    "end_time": normalize_time(shift.get("end_time")),
                    "required_role": shift["required_role"],
                    "template_name": shift["shift_templates"]["name"],
                }
            )
        rows.sort(key=lambda item: (item["shift_date"], item["start_time"]))
        return rows

    clauses = ["e.status = 'active'"]
    params: list[Any] = []
    if employee_name:
        clauses.append("e.name LIKE ?")
        params.append(f"%{employee_name}%")
    if shift_date:
        clauses.append("sh.shift_date = ?")
        params.append(shift_date)

    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT e.name AS employee_name, e.role, e.scheduled_hours,
                   st.name AS store_name, sh.id AS shift_id,
                   sh.shift_date, sh.start_time, sh.end_time,
                   sh.required_role, tpl.name AS template_name
            FROM shift_assignments sa
            JOIN employees e ON e.id = sa.employee_id
            JOIN shifts sh ON sh.id = sa.shift_id
            JOIN stores st ON st.id = sh.store_id
            JOIN shift_templates tpl ON tpl.id = sh.template_id
            WHERE {' AND '.join(clauses)}
            ORDER BY sh.shift_date, sh.start_time
            LIMIT 20
            """,
            params,
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def assign_employee_to_shift(
    store_id: str,
    shift_id: str,
    employee_id: str,
    requested_by: str = "manager",
    reason: str = "页面确认补位",
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    if use_supabase():
        client = supabase_client()
        store_rows = (
            client.table("stores")
            .select("id, external_id")
            .eq("external_id", store_id)
            .limit(1)
            .execute()
            .data
        )
        shift_rows = (
            client.table("shifts")
            .select(
                "id, external_id, store_id, shift_date, start_time, end_time, required_role, "
                "required_count, assigned_count, status, shift_templates(name)"
            )
            .eq("external_id", shift_id)
            .limit(1)
            .execute()
            .data
        )
        employee_rows = (
            client.table("employees")
            .select(
                "id, external_id, store_id, name, role, skills, weekly_hour_limit, scheduled_hours, "
                "can_close, can_float, status"
            )
            .eq("external_id", employee_id)
            .eq("status", "active")
            .limit(1)
            .execute()
            .data
        )
        if not store_rows or not shift_rows or not employee_rows:
            raise ValueError("门店、班次或员工不存在。")
        store = store_rows[0]
        shift = shift_rows[0]
        employee = employee_rows[0]
        if shift["store_id"] != store["id"] or employee["store_id"] != store["id"]:
            raise ValueError("员工或班次不属于当前门店。")
        if shift["assigned_count"] >= shift["required_count"]:
            raise ValueError("这个班次已经满员。")
        normalized_shift = {
            "id": shift["external_id"],
            "shift_date": shift["shift_date"],
            "start_time": normalize_time(shift.get("start_time")),
            "end_time": normalize_time(shift.get("end_time")),
            "required_role": shift["required_role"],
            "template_name": (shift.get("shift_templates") or {}).get("name", ""),
        }
        normalized_employee = normalize_employee({"stores": {"external_id": store_id}, **employee})
        risk_flags = evaluate_assignment_risks(store_id, normalized_shift, normalized_employee)
        if risk_flags:
            raise ValueError("；".join(risk_flags))

        assignment_id = _external_id("assign")
        change_id = _external_id("change")
        client.table("shift_assignments").insert(
            {
                "external_id": assignment_id,
                "shift_id": shift["id"],
                "employee_id": employee["id"],
                "assignment_status": "assigned",
                "source": "assistant",
            }
        ).execute()
        next_assigned_count = int(shift["assigned_count"]) + 1
        next_status = "filled" if next_assigned_count >= int(shift["required_count"]) else "open"
        client.table("shifts").update(
            {
                "assigned_count": next_assigned_count,
                "status": next_status,
            }
        ).eq("id", shift["id"]).execute()
        client.table("employees").update(
            {
                "scheduled_hours": float(employee["scheduled_hours"]) + _shift_hours(shift),
            }
        ).eq("id", employee["id"]).execute()
        client.table("shift_change_records").insert(
            {
                "external_id": change_id,
                "store_id": store["id"],
                "shift_id": shift["id"],
                "request_type": "cover",
                "target_employee_id": employee["id"],
                "reason": reason,
                "risk_flags": [],
                "approval_status": "approved",
                "requested_by": requested_by,
            }
        ).execute()
        result = {
            "assignment_id": assignment_id,
            "change_record_id": change_id,
            "shift_id": shift_id,
            "employee_id": employee_id,
            "assigned_count": next_assigned_count,
            "status": next_status,
            "risk_flags": risk_flags,
        }
        create_audit_log(
            action="assign_shift",
            user_id=actor_user_id,
            store_id=store_id,
            shift_id=shift_id,
            employee_id=employee_id,
            payload={"reason": reason, "requested_by": requested_by, "risk_flags": risk_flags},
            result=result,
        )
        return result

    now = "2026-08-11T00:00:00"
    assignment_id = _external_id("assign")
    change_id = _external_id("change")
    with connect() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        shift_row = conn.execute(
            "SELECT * FROM shifts WHERE id = ? AND store_id = ?",
            (shift_id, store_id),
        ).fetchone()
        employee_row = conn.execute(
            "SELECT * FROM employees WHERE id = ? AND store_id = ? AND status = 'active'",
            (employee_id, store_id),
        ).fetchone()
        if not shift_row or not employee_row:
            raise ValueError("门店、班次或员工不存在。")
        shift = row_to_dict(shift_row)
        employee = row_to_dict(employee_row)
        if shift["assigned_count"] >= shift["required_count"]:
            raise ValueError("这个班次已经满员。")
        risk_flags = evaluate_assignment_risks(store_id, shift, employee)
        if risk_flags:
            raise ValueError("；".join(risk_flags))
        existing = conn.execute(
            "SELECT id FROM shift_assignments WHERE shift_id = ? AND employee_id = ?",
            (shift_id, employee_id),
        ).fetchone()
        if existing:
            raise ValueError("这个员工已经在该班次中。")
        conn.execute(
            """
            INSERT INTO shift_assignments (id, shift_id, employee_id, assignment_status, source, created_at)
            VALUES (?, ?, ?, 'assigned', 'assistant', ?)
            """,
            (assignment_id, shift_id, employee_id, now),
        )
        next_assigned_count = int(shift["assigned_count"]) + 1
        next_status = "filled" if next_assigned_count >= int(shift["required_count"]) else "open"
        conn.execute(
            "UPDATE shifts SET assigned_count = ?, status = ? WHERE id = ?",
            (next_assigned_count, next_status, shift_id),
        )
        conn.execute(
            "UPDATE employees SET scheduled_hours = ? WHERE id = ?",
            (int(employee["scheduled_hours"]) + _shift_hours(shift), employee_id),
        )
        conn.execute(
            """
            INSERT INTO shift_change_records
              (id, store_id, shift_id, request_type, original_employee_id, target_employee_id,
               reason, risk_flags, approval_status, requested_by, requested_at, resolved_at)
            VALUES (?, ?, ?, 'cover', NULL, ?, ?, '[]', 'approved', ?, ?, ?)
            """,
        (change_id, store_id, shift_id, employee_id, reason, requested_by, now, now),
        )
        conn.commit()
    return {
        "assignment_id": assignment_id,
        "change_record_id": change_id,
        "shift_id": shift_id,
        "employee_id": employee_id,
        "assigned_count": next_assigned_count,
        "status": next_status,
        "risk_flags": risk_flags,
    }
