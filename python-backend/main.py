from __future__ import annotations

import csv
import io
import logging
import os
from datetime import date
from typing import Any
from uuid import uuid4

from agents import (
    ItemHelpers,
    MessageOutputItem,
    Runner,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from airline.agents import triage_agent
from airline.context import AirlineAgentChatContext, create_initial_context, public_context
from airline import schedule_repository

load_dotenv()

logger = logging.getLogger(__name__)

# Disable OpenAI platform tracing before any agents/OpenInference instrumentation
# initializes, otherwise the default exporter may boot and fail in local setups.
set_tracing_disabled(True)

LANGFUSE_ENABLED = all(
    os.getenv(key)
    for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
)
langfuse = None
propagate_attributes = None
LANGFUSE_AUTH_OK = False

if LANGFUSE_ENABLED:
    from langfuse import get_client, propagate_attributes
    from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor

    OpenAIAgentsInstrumentor().instrument()
    langfuse = get_client()
    try:
        LANGFUSE_AUTH_OK = bool(langfuse.auth_check())
        if not LANGFUSE_AUTH_OK:
            logger.warning("Langfuse credentials are present, but auth_check() failed.")
    except Exception as exc:
        LANGFUSE_AUTH_OK = False
        logger.warning("Langfuse auth_check() failed during startup: %s", exc)

from openai import AsyncOpenAI

app = FastAPI(title="Scheduling Assistant Demo")


def _cors_origins() -> list[str]:
    configured = os.getenv("FRONTEND_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://ui-three-red.vercel.app",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise RuntimeError(
        "Missing API key. Set OPENAI_API_KEY or DEEPSEEK_API_KEY in your environment or .env file."
    )

client = AsyncOpenAI(
    api_key=api_key,
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
)

set_default_openai_client(client, use_for_tracing=False)
set_default_openai_api("chat_completions")

SESSION_STORE: dict[str, Any] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    status: str
    agent: str
    output_text: str
    raw_output: Any
    context: dict[str, Any]
    trace_id: str | None = None
    trace_url: str | None = None


class FeedbackRequest(BaseModel):
    trace_id: str
    value: int
    comment: str | None = None


class FeedbackResponse(BaseModel):
    ok: bool


class AssignmentRequest(BaseModel):
    employee_id: str
    requested_by: str = "manager"
    reason: str = "页面确认补位"


class AssignmentResponse(BaseModel):
    ok: bool
    assignment_id: str
    change_record_id: str
    shift_id: str
    employee_id: str
    assigned_count: int
    status: str
    risk_flags: list[str] = []


class StoreResponse(BaseModel):
    id: str
    brand: str
    name: str
    city: str
    district: str
    address: str
    business_type: str
    opening_time: str
    closing_time: str
    status: str


class EmployeeResponse(BaseModel):
    id: str
    store_id: str
    name: str
    role: str
    skills: list[str]
    weekly_hour_limit: int
    scheduled_hours: int
    can_close: bool
    can_float: bool
    phone: str
    status: str


class ShiftResponse(BaseModel):
    id: str
    store_id: str
    template_id: str
    template_name: str
    shift_date: str
    start_time: str
    end_time: str
    required_role: str
    required_count: int
    assigned_count: int
    open_count: int
    status: str
    note: str | None = None


class ForecastResponse(BaseModel):
    id: str
    store_id: str
    store_name: str
    forecast_date: str
    hour: int
    role: str
    model_name: str
    model_version: str
    predicted_labor_hours: float
    baseline_labor_hours: float
    actual_labor_hours: float | None = None
    deviation_rate: float | None = None
    absolute_error: float | None = None
    status: str
    confidence: str
    features: dict[str, Any]
    notes: str | None = None


class ForecastSummaryResponse(BaseModel):
    store_count: int
    forecast_count: int
    evaluated_count: int
    badcase_count: int
    total_predicted_labor_hours: float
    total_actual_labor_hours: float
    average_abs_deviation_rate: float
    model_name: str
    model_version: str
    next_focus: list[ForecastResponse]


class MetricsImportRequest(BaseModel):
    csv_text: str


class MetricsImportResponse(BaseModel):
    ok: bool
    imported_count: int
    forecast_count: int
    badcase_count: int
    message: str
    required_columns: list[str]


REQUIRED_METRIC_COLUMNS = [
    "metric_date",
    "hour",
    "role",
    "order_count",
    "sales_amount",
    "actual_labor_hours",
]


def _store_from_row(row: dict[str, Any]) -> StoreResponse:
    return StoreResponse(
        id=row["id"],
        brand=row["brand"],
        name=row["name"],
        city=row["city"],
        district=row["district"],
        address=row["address"],
        business_type=row["business_type"],
        opening_time=row["opening_time"],
        closing_time=row["closing_time"],
        status=row["status"],
    )


def _employee_from_row(row: dict[str, Any]) -> EmployeeResponse:
    return EmployeeResponse(
        id=row["id"],
        store_id=row["store_id"],
        name=row["name"],
        role=row["role"],
        skills=row["skills"],
        weekly_hour_limit=row["weekly_hour_limit"],
        scheduled_hours=row["scheduled_hours"],
        can_close=bool(row["can_close"]),
        can_float=bool(row["can_float"]),
        phone=row["phone"],
        status=row["status"],
    )


def _shift_from_row(row: dict[str, Any]) -> ShiftResponse:
    required_count = row["required_count"]
    assigned_count = row["assigned_count"]
    return ShiftResponse(
        id=row["id"],
        store_id=row["store_id"],
        template_id=row["template_id"],
        template_name=row["template_name"],
        shift_date=row["shift_date"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        required_role=row["required_role"],
        required_count=required_count,
        assigned_count=assigned_count,
        open_count=max(required_count - assigned_count, 0),
        status=row["status"],
        note=row["note"],
    )


def _forecast_from_row(row: dict[str, Any]) -> ForecastResponse:
    return ForecastResponse(
        id=row["id"],
        store_id=row["store_id"],
        store_name=row["store_name"],
        forecast_date=row["forecast_date"],
        hour=row["hour"],
        role=row["role"],
        model_name=row["model_name"],
        model_version=row["model_version"],
        predicted_labor_hours=row["predicted_labor_hours"],
        baseline_labor_hours=row["baseline_labor_hours"],
        actual_labor_hours=row.get("actual_labor_hours"),
        deviation_rate=row.get("deviation_rate"),
        absolute_error=row.get("absolute_error"),
        status=row["status"],
        confidence=row["confidence"],
        features=row["features"],
        notes=row.get("notes"),
    )


def _langfuse_tags() -> list[str]:
    tags = [
        "shiftflow",
        "schedule-assistant",
        "fastapi",
    ]
    app_env = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT")
    if app_env:
        tags.append(f"env:{app_env}")
    return tags


def _langfuse_metadata(session_id: str, payload: ChatRequest) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "feature": "schedule-chat",
        "surface": "fastapi",
        "session_id": session_id,
    }
    app_env = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT")
    if app_env:
        metadata["environment"] = app_env
    if payload.session_id:
        metadata["existing_session"] = True
    return metadata


def _build_output(result: Any) -> str:
    message_parts = [
        ItemHelpers.text_message_output(item)
        for item in result.new_items
        if isinstance(item, MessageOutputItem)
    ]
    output_text = "\n".join(part for part in message_parts if part).strip()
    if not output_text:
        output_text = (
            result.final_output
            if isinstance(result.final_output, str)
            else str(result.final_output)
        )
    return output_text


def _classify_status(output_text: str) -> str:
    lowered = output_text.lower()
    status = "info"
    if "assignment blocked" in lowered or "blocked" in lowered:
        status = "blocked"
    elif "warning:" in lowered:
        status = "warning"
    elif any(
        phrase in lowered for phrase in ["assigned ", "removed ", "open shifts:", "is assigned to"]
    ):
        status = "success"
    return status


def _require_write_token(token: str | None) -> None:
    expected_token = os.getenv("SHIFT_WRITE_TOKEN")
    if not expected_token:
        raise HTTPException(status_code=503, detail="Write actions are not enabled.")
    if token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid write token.")


def _auth_required_for_writes() -> bool:
    return os.getenv("REQUIRE_SUPABASE_AUTH_FOR_WRITES", "").lower() in {"1", "true", "yes"}


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def _authorize_store_write(store_id: str, authorization: str | None) -> str | None:
    if not _auth_required_for_writes():
        return None
    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing Supabase access token.")
    try:
        user = schedule_repository.verify_supabase_user(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if not schedule_repository.user_can_write_store(user["id"], store_id):
        raise HTTPException(status_code=403, detail="你没有权限修改这个门店。")
    return user["id"]


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "是", "周末", "节假日", "促销"}


def _parse_metrics_csv(csv_text: str) -> list[dict[str, Any]]:
    try:
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
    except csv.Error as exc:
        raise ValueError(f"CSV 解析失败：{exc}") from exc
    if not reader.fieldnames:
        raise ValueError("CSV 需要包含表头。")

    missing = [column for column in REQUIRED_METRIC_COLUMNS if column not in reader.fieldnames]
    if missing:
        raise ValueError(f"CSV 缺少必要字段：{', '.join(missing)}。")

    metrics = []
    for index, row in enumerate(reader, start=2):
        try:
            metric_date = date.fromisoformat(str(row["metric_date"]).strip()).isoformat()
            hour = int(str(row["hour"]).strip())
            if hour < 0 or hour > 23:
                raise ValueError("hour 必须在 0-23 之间")
            role = str(row["role"]).strip()
            if not role:
                raise ValueError("role 不能为空")
            order_count = int(float(str(row["order_count"]).strip()))
            sales_amount = float(str(row["sales_amount"]).strip())
            actual_labor_hours = float(str(row["actual_labor_hours"]).strip())
            if order_count < 0 or sales_amount < 0 or actual_labor_hours < 0:
                raise ValueError("订单量、销售额、实际工时不能为负数")
            metrics.append(
                {
                    "metric_date": metric_date,
                    "hour": hour,
                    "role": role,
                    "order_count": order_count,
                    "sales_amount": sales_amount,
                    "weather": (row.get("weather") or "clear").strip() or "clear",
                    "temperature": float(row["temperature"]) if row.get("temperature") not in {None, ""} else None,
                    "is_weekend": _parse_bool(row.get("is_weekend")),
                    "is_holiday": _parse_bool(row.get("is_holiday")),
                    "promotion_flag": _parse_bool(row.get("promotion_flag")),
                    "actual_labor_hours": actual_labor_hours,
                }
            )
        except Exception as exc:
            raise ValueError(f"第 {index} 行数据不合法：{exc}") from exc

    if not metrics:
        raise ValueError("CSV 没有可导入的数据行。")
    if len(metrics) > 1000:
        raise ValueError("单次最多导入 1000 行，请拆分文件后再试。")
    return metrics


@app.get("/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "data_source": "supabase" if schedule_repository.use_supabase() else "sqlite",
        "langfuse_enabled": LANGFUSE_ENABLED,
        "langfuse_auth_ok": LANGFUSE_AUTH_OK if LANGFUSE_ENABLED else False,
        "write_auth_required": _auth_required_for_writes(),
    }


@app.get("/stores", response_model=list[StoreResponse])
async def list_stores() -> list[StoreResponse]:
    rows = schedule_repository.list_stores()
    return [_store_from_row(row) for row in rows]


@app.get("/stores/{store_id}/staff", response_model=list[EmployeeResponse])
async def list_store_staff(store_id: str) -> list[EmployeeResponse]:
    if not any(store["id"] == store_id for store in schedule_repository.list_stores()):
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found.")
    rows = schedule_repository.list_store_staff(store_id)
    return [_employee_from_row(row) for row in rows]


@app.get("/stores/{store_id}/shifts", response_model=list[ShiftResponse])
async def list_store_shifts(
    store_id: str,
    shift_date: str | None = Query(default=None, description="Optional date filter, YYYY-MM-DD."),
    status: str | None = Query(default=None, description="Optional status filter, e.g. open or filled."),
) -> list[ShiftResponse]:
    if not any(store["id"] == store_id for store in schedule_repository.list_stores()):
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found.")
    rows = schedule_repository.list_store_shifts(store_id, shift_date=shift_date, status=status)
    return [_shift_from_row(row) for row in rows]


@app.get("/forecasts/summary", response_model=ForecastSummaryResponse)
async def get_forecast_summary(
    store_id: str | None = Query(default=None, description="Optional store external id filter."),
) -> ForecastSummaryResponse:
    if store_id and not any(store["id"] == store_id for store in schedule_repository.list_stores()):
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found.")
    summary = schedule_repository.get_forecast_summary(store_id=store_id)
    summary["next_focus"] = [_forecast_from_row(row) for row in summary["next_focus"]]
    return ForecastSummaryResponse(**summary)


@app.get("/stores/{store_id}/forecasts", response_model=list[ForecastResponse])
async def list_store_forecasts(
    store_id: str,
    forecast_date: str | None = Query(default=None, description="Optional date filter, YYYY-MM-DD."),
) -> list[ForecastResponse]:
    if not any(store["id"] == store_id for store in schedule_repository.list_stores()):
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found.")
    rows = schedule_repository.list_store_forecasts(store_id, forecast_date=forecast_date)
    return [_forecast_from_row(row) for row in rows]


@app.post("/stores/{store_id}/metrics/import-csv", response_model=MetricsImportResponse)
async def import_store_metrics_csv(
    store_id: str,
    payload: MetricsImportRequest,
    x_shift_write_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> MetricsImportResponse:
    _require_write_token(x_shift_write_token)
    actor_user_id = _authorize_store_write(store_id, authorization)
    if not any(store["id"] == store_id for store in schedule_repository.list_stores()):
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found.")
    try:
        metrics = _parse_metrics_csv(payload.csv_text)
        result = schedule_repository.import_hourly_metrics(
            store_id=store_id,
            metrics=metrics,
            actor_user_id=actor_user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MetricsImportResponse(
        ok=True,
        message="导入完成，已刷新静默预测。",
        required_columns=REQUIRED_METRIC_COLUMNS,
        **result,
    )


@app.post("/stores/{store_id}/shifts/{shift_id}/assignments", response_model=AssignmentResponse)
async def assign_store_shift(
    store_id: str,
    shift_id: str,
    payload: AssignmentRequest,
    x_shift_write_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> AssignmentResponse:
    _require_write_token(x_shift_write_token)
    actor_user_id = _authorize_store_write(store_id, authorization)
    if not any(store["id"] == store_id for store in schedule_repository.list_stores()):
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found.")
    try:
        result = schedule_repository.assign_employee_to_shift(
            store_id=store_id,
            shift_id=shift_id,
            employee_id=payload.employee_id,
            requested_by=payload.requested_by,
            reason=payload.reason,
            actor_user_id=actor_user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AssignmentResponse(ok=True, **result)


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    session_id = payload.session_id or uuid4().hex
    state = SESSION_STORE.get(session_id)
    if state is None:
        state = create_initial_context()
        SESSION_STORE[session_id] = state

    context = AirlineAgentChatContext(state=state)
    trace_id: str | None = None
    trace_url: str | None = None

    if LANGFUSE_ENABLED and langfuse is not None and propagate_attributes is not None:
        with langfuse.start_as_current_observation(
            as_type="span",
            name="schedule-chat-turn",
        ) as root_span:
            with propagate_attributes(
                session_id=session_id,
                tags=_langfuse_tags(),
                metadata=_langfuse_metadata(session_id, payload),
            ):
                root_span.update(
                    input=payload.message
                )
                try:
                    result = await Runner.run(
                        triage_agent,
                        input=payload.message,
                        context=context,
                    )
                    output_text = _build_output(result)
                    status = _classify_status(output_text)
                    root_span.update(
                        output=output_text,
                        metadata={
                            "agent": result.last_agent.name if result.last_agent else triage_agent.name,
                            "status": status,
                            "response_preview": output_text[:200],
                        },
                        level="ERROR" if status == "blocked" else "WARNING" if status == "warning" else "DEFAULT",
                        status_message=output_text[:200],
                    )
                    trace_id = langfuse.get_current_trace_id()
                    if trace_id and LANGFUSE_AUTH_OK and hasattr(langfuse, "get_trace_url"):
                        try:
                            trace_url = langfuse.get_trace_url(trace_id=trace_id)
                        except Exception as exc:
                            logger.warning("Failed to build Langfuse trace URL: %s", exc)
                except Exception as exc:
                    root_span.update(
                        output=str(exc),
                        level="ERROR",
                        status_message=str(exc),
                        metadata={"error_type": type(exc).__name__},
                    )
                    trace_id = langfuse.get_current_trace_id()
                    if trace_id and LANGFUSE_AUTH_OK and hasattr(langfuse, "get_trace_url"):
                        try:
                            trace_url = langfuse.get_trace_url(trace_id=trace_id)
                        except Exception as exc:
                            logger.warning("Failed to build Langfuse trace URL after error: %s", exc)
                    raise
    else:
        result = await Runner.run(
            triage_agent,
            input=payload.message,
            context=context,
        )
        output_text = _build_output(result)
        status = _classify_status(output_text)

    return ChatResponse(
        session_id=session_id,
        status=status,
        agent=result.last_agent.name if result.last_agent else triage_agent.name,
        output_text=output_text,
        raw_output=result.final_output,
        context=public_context(context.state),
        trace_id=trace_id,
        trace_url=trace_url,
    )


@app.post("/feedback", response_model=FeedbackResponse)
async def feedback(payload: FeedbackRequest) -> FeedbackResponse:
    if not LANGFUSE_ENABLED or langfuse is None:
        raise RuntimeError("Langfuse is not enabled for this backend.")

    langfuse.create_score(
        name="user-thumbs",
        value=float(payload.value),
        trace_id=payload.trace_id,
        data_type="BOOLEAN",
        comment=payload.comment,
    )
    langfuse.flush()
    return FeedbackResponse(ok=True)


@app.on_event("shutdown")
async def shutdown_flush_langfuse() -> None:
    if LANGFUSE_ENABLED and langfuse is not None:
        langfuse.flush()
