from __future__ import annotations as _annotations

from copy import deepcopy

from .context import AirlineAgentContext

MOCK_SCHEDULES = {
    "icu_week": {
        "name": "ICU weekly roster",
        "team_name": "ICU",
        "employee_name": "张琳",
        "role_name": "Registered Nurse",
        "schedule_date": "2026-07-20",
        "shift_id": "ICU-2026-07-20-DAY",
        "shift_time": "07:00-15:00",
        "roster": [
            {
                "employee_name": "张琳",
                "employee_id": "RN-201",
                "team_name": "ICU",
                "schedule_date": "2026-07-20",
                "shift_id": "ICU-2026-07-20-DAY",
                "shift_time": "07:00-15:00",
                "role_name": "Registered Nurse",
                "status": "Assigned",
            },
            {
                "employee_name": "王涛",
                "employee_id": "RN-188",
                "team_name": "ICU",
                "schedule_date": "2026-07-20",
                "shift_id": "ICU-2026-07-20-NIGHT",
                "shift_time": "23:00-07:00",
                "role_name": "Charge Nurse",
                "status": "Assigned",
            },
            {
                "employee_name": "王涛",
                "employee_id": "RN-188",
                "team_name": "ICU",
                "schedule_date": "2026-07-19",
                "shift_id": "ICU-2026-07-19-NIGHT",
                "shift_time": "23:00-07:00",
                "role_name": "Charge Nurse",
                "status": "Assigned",
            },
            {
                "employee_name": "李敏",
                "employee_id": "RN-233",
                "team_name": "ICU",
                "schedule_date": "2026-07-21",
                "shift_id": "ICU-2026-07-21-DAY",
                "shift_time": "07:00-15:00",
                "role_name": "Registered Nurse",
                "status": "Assigned",
            },
            {
                "employee_name": "李敏",
                "employee_id": "RN-233",
                "team_name": "ICU",
                "schedule_date": "2026-07-18",
                "shift_id": "ICU-2026-07-18-DAY",
                "shift_time": "07:00-15:00",
                "role_name": "Registered Nurse",
                "status": "Assigned",
            },
            {
                "employee_name": "李敏",
                "employee_id": "RN-233",
                "team_name": "ICU",
                "schedule_date": "2026-07-19",
                "shift_id": "ICU-2026-07-19-DAY",
                "shift_time": "07:00-15:00",
                "role_name": "Registered Nurse",
                "status": "Assigned",
            },
            {
                "employee_name": "李敏",
                "employee_id": "RN-233",
                "team_name": "ICU",
                "schedule_date": "2026-07-20",
                "shift_id": "ICU-2026-07-20-EVE",
                "shift_time": "15:00-23:00",
                "role_name": "Registered Nurse",
                "status": "Assigned",
            },
        ],
        "open_shifts": [
            {
                "shift_id": "ICU-2026-07-21-NIGHT",
                "team_name": "ICU",
                "schedule_date": "2026-07-21",
                "shift_time": "23:00-07:00",
                "role_name": "Registered Nurse",
                "status": "Open",
                "note": "Need one more ICU-certified nurse",
            },
            {
                "shift_id": "ICU-2026-07-22-DAY",
                "team_name": "ICU",
                "schedule_date": "2026-07-22",
                "shift_time": "07:00-15:00",
                "role_name": "Registered Nurse",
                "status": "Open",
                "note": "Backfill for approved leave",
            },
        ],
    },
    "store_week": {
        "name": "Retail store roster",
        "team_name": "Store Ops",
        "employee_name": "陈宇",
        "role_name": "Floor Supervisor",
        "schedule_date": "2026-07-20",
        "shift_id": "STORE-2026-07-20-AM",
        "shift_time": "09:00-17:00",
        "roster": [
            {
                "employee_name": "陈宇",
                "employee_id": "ST-101",
                "team_name": "Store Ops",
                "schedule_date": "2026-07-20",
                "shift_id": "STORE-2026-07-20-AM",
                "shift_time": "09:00-17:00",
                "role_name": "Floor Supervisor",
                "status": "Assigned",
            },
            {
                "employee_name": "赵可",
                "employee_id": "ST-118",
                "team_name": "Store Ops",
                "schedule_date": "2026-07-20",
                "shift_id": "STORE-2026-07-20-PM",
                "shift_time": "13:00-21:00",
                "role_name": "Cashier",
                "status": "Assigned",
            },
        ],
        "open_shifts": [
            {
                "shift_id": "STORE-2026-07-21-PM",
                "team_name": "Store Ops",
                "schedule_date": "2026-07-21",
                "shift_time": "13:00-21:00",
                "role_name": "Cashier",
                "status": "Open",
                "note": "Can be picked up by trained cashier or supervisor",
            }
        ],
    },
}


def apply_itinerary_defaults(ctx: AirlineAgentContext, scenario_key: str | None = None) -> None:
    """Populate the context with a demo schedule if missing."""
    target_key = scenario_key or ctx.scenario or "icu_week"
    data = MOCK_SCHEDULES.get(target_key) or next(iter(MOCK_SCHEDULES.values()))
    ctx.scenario = target_key
    ctx.employee_name = ctx.employee_name or data.get("employee_name")
    ctx.team_name = ctx.team_name or data.get("team_name")
    ctx.role_name = ctx.role_name or data.get("role_name")
    ctx.schedule_date = ctx.schedule_date or data.get("schedule_date")
    ctx.shift_id = ctx.shift_id or data.get("shift_id")
    ctx.shift_time = ctx.shift_time or data.get("shift_time")
    if ctx.roster is None:
        ctx.roster = deepcopy(data.get("roster", []))
    if ctx.open_shifts is None:
        ctx.open_shifts = deepcopy(data.get("open_shifts", []))


def get_itinerary_for_flight(shift_id: str | None) -> tuple[str, dict] | None:
    """Backwards-compatible helper: resolve a mock schedule from a shift id."""
    if not shift_id:
        return None
    for key, schedule in MOCK_SCHEDULES.items():
        for shift in schedule.get("roster", []):
            if shift.get("shift_id", "").lower() == shift_id.lower():
                return key, schedule
        for shift in schedule.get("open_shifts", []):
            if shift.get("shift_id", "").lower() == shift_id.lower():
                return key, schedule
    return None


def active_itinerary(ctx: AirlineAgentContext) -> tuple[str, dict]:
    """Resolve the active mock schedule for the current context."""
    if ctx.scenario and ctx.scenario in MOCK_SCHEDULES:
        return ctx.scenario, MOCK_SCHEDULES[ctx.scenario]
    match = get_itinerary_for_flight(ctx.shift_id)
    if match:
        ctx.scenario = match[0]
        return match
    ctx.scenario = "icu_week"
    return ctx.scenario, MOCK_SCHEDULES["icu_week"]
