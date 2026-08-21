from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class PredictionRow:
    metric_date: str
    hour: int
    role: str
    actual_labor_hours: float
    predicted_labor_hours: float
    absolute_error: float
    absolute_percentage_error: float


@dataclass(frozen=True)
class ModelEvaluation:
    row_count: int
    train_count: int
    test_count: int
    train_max_date: str
    test_min_date: str
    leakage_free: bool
    mae: float
    mape: float
    badcase_rate: float
    min_prediction: float
    max_prediction: float
    prediction_signature: str
    predictions: list[PredictionRow]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}


def normalize_metric(row: dict[str, Any]) -> dict[str, Any]:
    metric_date = date.fromisoformat(str(row["metric_date"])).isoformat()
    hour = int(row["hour"])
    if hour < 0 or hour > 23:
        raise ValueError("hour must be between 0 and 23")
    actual = float(row["actual_labor_hours"])
    if actual < 0:
        raise ValueError("actual_labor_hours must be non-negative")
    return {
        "metric_date": metric_date,
        "hour": hour,
        "role": str(row["role"]).strip(),
        "order_count": int(float(row.get("order_count", 0))),
        "sales_amount": float(row.get("sales_amount", 0)),
        "weather": str(row.get("weather") or "clear").strip().lower(),
        "temperature": float(row["temperature"]) if row.get("temperature") not in {None, ""} else None,
        "is_weekend": _as_bool(row.get("is_weekend")),
        "is_holiday": _as_bool(row.get("is_holiday")),
        "promotion_flag": _as_bool(row.get("promotion_flag")),
        "actual_labor_hours": actual,
    }


def temporal_train_test_split(
    rows: list[dict[str, Any]],
    test_ratio: float = 0.25,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(rows) < 4:
        raise ValueError("at least 4 metric rows are required")
    normalized = sorted((normalize_metric(row) for row in rows), key=lambda item: (item["metric_date"], item["hour"], item["role"]))
    dates = sorted({row["metric_date"] for row in normalized})
    if len(dates) < 2:
        raise ValueError("at least 2 metric dates are required for leakage-free evaluation")
    test_date_count = max(1, round(len(dates) * test_ratio))
    split_date = dates[-test_date_count]
    train = [row for row in normalized if row["metric_date"] < split_date]
    test = [row for row in normalized if row["metric_date"] >= split_date]
    if not train or not test:
        raise ValueError("temporal split produced an empty train or test set")
    return train, test


def _adjustment_factor(row: dict[str, Any]) -> float:
    factor = 1.0
    if row["is_weekend"]:
        factor += 0.08
    if row["is_holiday"]:
        factor += 0.12
    if row["promotion_flag"]:
        factor += 0.10
    if row["weather"] in {"rain", "小雨", "大雨", "雨"}:
        factor += 0.04
    return factor


def fit_baseline_model(train_rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[int, str], list[float]] = defaultdict(list)
    role_grouped: dict[str, list[float]] = defaultdict(list)
    values = []
    for row in train_rows:
        actual = float(row["actual_labor_hours"])
        grouped[(int(row["hour"]), row["role"])].append(actual)
        role_grouped[row["role"]].append(actual)
        values.append(actual)
    if not values:
        raise ValueError("cannot train on empty rows")
    return {
        "hour_role_mean": {f"{hour}|{role}": sum(items) / len(items) for (hour, role), items in grouped.items()},
        "role_mean": {role: sum(items) / len(items) for role, items in role_grouped.items()},
        "global_mean": sum(values) / len(values),
    }


def predict_one(model: dict[str, Any], row: dict[str, Any]) -> float:
    key = f"{int(row['hour'])}|{row['role']}"
    baseline = model["hour_role_mean"].get(key)
    if baseline is None:
        baseline = model["role_mean"].get(row["role"], model["global_mean"])
    return max(float(baseline) * _adjustment_factor(row), 0.0)


def evaluate_labor_forecast(rows: list[dict[str, Any]]) -> ModelEvaluation:
    train, test = temporal_train_test_split(rows)
    model = fit_baseline_model(train)
    predictions = []
    for row in test:
        predicted = predict_one(model, row)
        actual = float(row["actual_labor_hours"])
        absolute_error = abs(actual - predicted)
        absolute_percentage_error = absolute_error / actual if actual else 0.0
        predictions.append(
            PredictionRow(
                metric_date=row["metric_date"],
                hour=int(row["hour"]),
                role=row["role"],
                actual_labor_hours=round(actual, 4),
                predicted_labor_hours=round(predicted, 4),
                absolute_error=round(absolute_error, 4),
                absolute_percentage_error=round(absolute_percentage_error, 4),
            )
        )

    mae = sum(item.absolute_error for item in predictions) / len(predictions)
    mape = sum(item.absolute_percentage_error for item in predictions) / len(predictions)
    badcase_rate = sum(1 for item in predictions if item.absolute_percentage_error >= 0.25) / len(predictions)
    signature_payload = [
        {
            "date": item.metric_date,
            "hour": item.hour,
            "role": item.role,
            "prediction": item.predicted_labor_hours,
        }
        for item in predictions
    ]
    signature = hashlib.sha256(
        json.dumps(signature_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    train_max_date = max(row["metric_date"] for row in train)
    test_min_date = min(row["metric_date"] for row in test)
    prediction_values = [item.predicted_labor_hours for item in predictions]
    return ModelEvaluation(
        row_count=len(rows),
        train_count=len(train),
        test_count=len(test),
        train_max_date=train_max_date,
        test_min_date=test_min_date,
        leakage_free=train_max_date < test_min_date,
        mae=round(mae, 4),
        mape=round(mape, 4),
        badcase_rate=round(badcase_rate, 4),
        min_prediction=round(min(prediction_values), 4),
        max_prediction=round(max(prediction_values), 4),
        prediction_signature=signature,
        predictions=predictions,
    )
