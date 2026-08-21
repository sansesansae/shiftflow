from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SEED_JSON = ROOT / "python-backend" / "data" / "shiftflow_seed.json"
OUTPUT_SQL = Path(__file__).resolve().parent / "seed_shiftflow_demo.sql"

REQUEST_TYPE_MAP = {
    "补位": "cover",
    "换班": "swap",
    "请假后补班": "absence",
}

APPROVAL_STATUS_MAP = {
    "pending": "pending",
    "approved": "approved",
    "needs_review": "pending",
}


def sql_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def jsonb_literal(value: str | list[Any]) -> str:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = []
    else:
        parsed = value
    return sql_literal(json.dumps(parsed, ensure_ascii=False)) + "::jsonb"


def ref_id(table: str, external_id: str | None) -> str:
    if not external_id:
        return "null"
    return f"(select id from public.{table} where external_id = {sql_literal(external_id)})"


def values(rows: list[str]) -> str:
    return ",\n".join(rows)


def build_sql() -> str:
    data = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    lines: list[str] = [
        "-- ShiftFlow demo seed data for Supabase",
        "-- Run after supabase/migrations/001_shiftflow_schema.sql.",
        "begin;",
        "",
    ]

    store_rows = []
    for row in data["stores"]:
        store_rows.append(
            "("
            + values(
                [
                    sql_literal(row["id"]),
                    sql_literal(row["brand"]),
                    sql_literal(row["name"]),
                    sql_literal(row["city"]),
                    sql_literal(row["district"]),
                    sql_literal(row["address"]),
                    sql_literal(row["business_type"]),
                    sql_literal(row["opening_time"]),
                    sql_literal(row["closing_time"]),
                    sql_literal(row["status"]),
                    sql_literal(row["created_at"]),
                ]
            )
            + ")"
        )
    lines += [
        "insert into public.stores (external_id, brand, name, city, district, address, business_type, opening_time, closing_time, status, created_at)",
        "values",
        values(store_rows),
        "on conflict (external_id) do update set",
        "  brand = excluded.brand,",
        "  name = excluded.name,",
        "  city = excluded.city,",
        "  district = excluded.district,",
        "  address = excluded.address,",
        "  business_type = excluded.business_type,",
        "  opening_time = excluded.opening_time,",
        "  closing_time = excluded.closing_time,",
        "  status = excluded.status;",
        "",
    ]

    template_rows = []
    for row in data["shift_templates"]:
        template_rows.append(
            "("
            + values(
                [
                    sql_literal(row["id"]),
                    sql_literal(row["name"]),
                    sql_literal(row["start_time"]),
                    sql_literal(row["end_time"]),
                    jsonb_literal(row["default_roles"]),
                    sql_literal(row["priority"]),
                ]
            )
            + ")"
        )
    lines += [
        "insert into public.shift_templates (external_id, name, start_time, end_time, default_roles, priority)",
        "values",
        values(template_rows),
        "on conflict (external_id) do update set",
        "  name = excluded.name,",
        "  start_time = excluded.start_time,",
        "  end_time = excluded.end_time,",
        "  default_roles = excluded.default_roles,",
        "  priority = excluded.priority;",
        "",
    ]

    employee_rows = []
    for row in data["employees"]:
        employee_rows.append(
            "("
            + values(
                [
                    sql_literal(row["id"]),
                    ref_id("stores", row["store_id"]),
                    sql_literal(row["name"]),
                    sql_literal(row["role"]),
                    jsonb_literal(row["skills"]),
                    sql_literal(row["weekly_hour_limit"]),
                    sql_literal(row["scheduled_hours"]),
                    sql_literal(bool(row["can_close"])),
                    sql_literal(bool(row["can_float"])),
                    sql_literal(row["phone"]),
                    sql_literal(row["status"]),
                    sql_literal(row["created_at"]),
                ]
            )
            + ")"
        )
    lines += [
        "insert into public.employees (external_id, store_id, name, role, skills, weekly_hour_limit, scheduled_hours, can_close, can_float, phone, status, created_at)",
        "values",
        values(employee_rows),
        "on conflict (external_id) do update set",
        "  store_id = excluded.store_id,",
        "  name = excluded.name,",
        "  role = excluded.role,",
        "  skills = excluded.skills,",
        "  weekly_hour_limit = excluded.weekly_hour_limit,",
        "  scheduled_hours = excluded.scheduled_hours,",
        "  can_close = excluded.can_close,",
        "  can_float = excluded.can_float,",
        "  phone = excluded.phone,",
        "  status = excluded.status;",
        "",
    ]

    shift_rows = []
    for row in data["shifts"]:
        shift_rows.append(
            "("
            + values(
                [
                    sql_literal(row["id"]),
                    ref_id("stores", row["store_id"]),
                    ref_id("shift_templates", row["template_id"]),
                    sql_literal(row["shift_date"]),
                    sql_literal(row["start_time"]),
                    sql_literal(row["end_time"]),
                    sql_literal(row["required_role"]),
                    sql_literal(row["required_count"]),
                    sql_literal(row["assigned_count"]),
                    sql_literal(row["status"]),
                    sql_literal(row.get("note") or None),
                    sql_literal(row["created_at"]),
                ]
            )
            + ")"
        )
    lines += [
        "insert into public.shifts (external_id, store_id, template_id, shift_date, start_time, end_time, required_role, required_count, assigned_count, status, note, created_at)",
        "values",
        values(shift_rows),
        "on conflict (external_id) do update set",
        "  store_id = excluded.store_id,",
        "  template_id = excluded.template_id,",
        "  shift_date = excluded.shift_date,",
        "  start_time = excluded.start_time,",
        "  end_time = excluded.end_time,",
        "  required_role = excluded.required_role,",
        "  required_count = excluded.required_count,",
        "  assigned_count = excluded.assigned_count,",
        "  status = excluded.status,",
        "  note = excluded.note;",
        "",
    ]

    assignment_rows = []
    for row in data["shift_assignments"]:
        assignment_rows.append(
            "("
            + values(
                [
                    sql_literal(row["id"]),
                    ref_id("shifts", row["shift_id"]),
                    ref_id("employees", row["employee_id"]),
                    sql_literal(row["assignment_status"]),
                    sql_literal("import" if row["source"] == "seed" else row["source"]),
                    sql_literal(row["created_at"]),
                ]
            )
            + ")"
        )
    lines += [
        "insert into public.shift_assignments (external_id, shift_id, employee_id, assignment_status, source, created_at)",
        "values",
        values(assignment_rows),
        "on conflict (external_id) do update set",
        "  shift_id = excluded.shift_id,",
        "  employee_id = excluded.employee_id,",
        "  assignment_status = excluded.assignment_status,",
        "  source = excluded.source;",
        "",
    ]

    change_rows = []
    for row in data["shift_change_records"]:
        change_rows.append(
            "("
            + values(
                [
                    sql_literal(row["id"]),
                    ref_id("stores", row["store_id"]),
                    ref_id("shifts", row["shift_id"]),
                    sql_literal(REQUEST_TYPE_MAP.get(row["request_type"], "modify")),
                    ref_id("employees", row.get("original_employee_id")),
                    ref_id("employees", row.get("target_employee_id")),
                    sql_literal(row["reason"]),
                    jsonb_literal(row["risk_flags"]),
                    sql_literal(APPROVAL_STATUS_MAP.get(row["approval_status"], "pending")),
                    sql_literal(row["requested_by"]),
                    sql_literal(row["requested_at"]),
                    sql_literal(row.get("resolved_at")),
                ]
            )
            + ")"
        )
    lines += [
        "insert into public.shift_change_records (external_id, store_id, shift_id, request_type, original_employee_id, target_employee_id, reason, risk_flags, approval_status, requested_by, requested_at, resolved_at)",
        "values",
        values(change_rows),
        "on conflict (external_id) do update set",
        "  store_id = excluded.store_id,",
        "  shift_id = excluded.shift_id,",
        "  request_type = excluded.request_type,",
        "  original_employee_id = excluded.original_employee_id,",
        "  target_employee_id = excluded.target_employee_id,",
        "  reason = excluded.reason,",
        "  risk_flags = excluded.risk_flags,",
        "  approval_status = excluded.approval_status,",
        "  requested_by = excluded.requested_by,",
        "  requested_at = excluded.requested_at,",
        "  resolved_at = excluded.resolved_at;",
        "",
        "commit;",
        "",
        "select",
        "  (select count(*) from public.stores) as stores,",
        "  (select count(*) from public.employees) as employees,",
        "  (select count(*) from public.shift_templates) as shift_templates,",
        "  (select count(*) from public.shifts) as shifts,",
        "  (select count(*) from public.shift_assignments) as shift_assignments,",
        "  (select count(*) from public.shift_change_records) as shift_change_records;",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    OUTPUT_SQL.write_text(build_sql(), encoding="utf-8")
    print(OUTPUT_SQL)
