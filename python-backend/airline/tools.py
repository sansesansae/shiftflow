from __future__ import annotations as _annotations

from copy import deepcopy
from datetime import datetime, timedelta

from agents import RunContextWrapper, function_tool

from .context import AirlineAgentChatContext
from .demo_data import active_itinerary, apply_itinerary_defaults
from . import schedule_repository


class ProgressUpdateEvent:
    def __init__(self, text: str):
        self.text = text


MAX_WEEKLY_HOURS = 40
MAX_CONSECUTIVE_NIGHTS = 2


def _parse_shift_hours(shift_time: str | None) -> tuple[float, float, float]:
    if not shift_time:
        return 0.0, 0.0, 0.0
    start_text, end_text = shift_time.split("-")
    start_hour, start_minute = map(int, start_text.split(":"))
    end_hour, end_minute = map(int, end_text.split(":"))
    start = start_hour + start_minute / 60
    end = end_hour + end_minute / 60
    if end <= start:
        end += 24
    return start, end, end - start


def _shift_is_night(shift: dict[str, str]) -> bool:
    shift_id = (shift.get("shift_id") or "").lower()
    shift_time = shift.get("shift_time") or ""
    return "night" in shift_id or shift_time.startswith("23:") or shift_time.endswith("07:00")


def _same_day_conflict(existing_shift: dict[str, str], candidate_shift: dict[str, str]) -> bool:
    if existing_shift.get("schedule_date") != candidate_shift.get("schedule_date"):
        return False
    existing_start, existing_end, _ = _parse_shift_hours(existing_shift.get("shift_time"))
    candidate_start, candidate_end, _ = _parse_shift_hours(candidate_shift.get("shift_time"))
    return existing_start < candidate_end and candidate_start < existing_end


def _weekly_hours(roster: list[dict[str, str]], employee_name: str, team_name: str | None) -> float:
    relevant = [
        shift for shift in roster
        if shift.get("employee_name") == employee_name
        and (team_name is None or shift.get("team_name") == team_name)
    ]
    return sum(_parse_shift_hours(shift.get("shift_time"))[2] for shift in relevant)


def _consecutive_night_streak(
    roster: list[dict[str, str]],
    employee_name: str,
    team_name: str | None,
    candidate_shift: dict[str, str],
) -> int:
    if not _shift_is_night(candidate_shift):
        return 0

    dates = {
        datetime.strptime(shift["schedule_date"], "%Y-%m-%d").date()
        for shift in roster
        if shift.get("employee_name") == employee_name
        and (team_name is None or shift.get("team_name") == team_name)
        and _shift_is_night(shift)
        and shift.get("schedule_date")
    }
    candidate_date = datetime.strptime(candidate_shift["schedule_date"], "%Y-%m-%d").date()
    dates.add(candidate_date)

    streak = 1
    cursor = candidate_date - timedelta(days=1)
    while cursor in dates:
        streak += 1
        cursor -= timedelta(days=1)

    cursor = candidate_date + timedelta(days=1)
    while cursor in dates:
        streak += 1
        cursor += timedelta(days=1)

    return streak


def _assignment_risk_message(
    roster: list[dict[str, str]],
    employee_name: str,
    candidate_shift: dict[str, str],
) -> str | None:
    conflicts = [
        shift for shift in roster
        if shift.get("employee_name") == employee_name and _same_day_conflict(shift, candidate_shift)
    ]
    if conflicts:
        shift = conflicts[0]
        return (
            f"Assignment blocked: {employee_name} already has {shift.get('shift_id')} on "
            f"{shift.get('schedule_date')} ({shift.get('shift_time')})."
        )

    projected_hours = _weekly_hours(roster, employee_name, candidate_shift.get("team_name")) + _parse_shift_hours(
        candidate_shift.get("shift_time")
    )[2]
    if projected_hours > MAX_WEEKLY_HOURS:
        return (
            f"Assignment blocked: {employee_name} would reach {projected_hours:.0f} scheduled hours this week, "
            f"above the {MAX_WEEKLY_HOURS}-hour guideline."
        )

    night_streak = _consecutive_night_streak(
        roster, employee_name, candidate_shift.get("team_name"), candidate_shift
    )
    if night_streak > MAX_CONSECUTIVE_NIGHTS:
        return (
            f"Assignment blocked: {employee_name} would reach {night_streak} consecutive night shifts, "
            f"above the {MAX_CONSECUTIVE_NIGHTS}-night limit."
        )

    return None


def _format_shift_time(shift: dict[str, str]) -> str:
    return f"{shift.get('start_time')}-{shift.get('end_time')}"


@function_tool(
    name_override="faq_lookup_tool",
    description_override="Lookup scheduling policies and operational FAQ answers.",
)
async def faq_lookup_tool(question: str) -> str:
    q = question.lower()
    if "night" in q or "夜班" in q:
        return "Night shifts should not be assigned for more than 2 consecutive days without supervisor approval and a recovery day."
    if "swap" in q or "换班" in q or "调班" in q:
        return "Shift swaps require both employees to have the right role coverage. The final schedule owner should confirm the replacement before publishing."
    if "leave" in q or "请假" in q:
        return "Approved leave should trigger a backfill search immediately. Priority goes to qualified staff with no overtime conflicts."
    if "overtime" in q or "加班" in q:
        return "Overtime should be reviewed once an employee exceeds 40 scheduled hours in a week or picks up a sixth consecutive shift."
    return "Current policy guidance covers shift swaps, approved leave backfills, overtime review, and consecutive night shift limits."


@function_tool(
    name_override="get_trip_details",
    description_override="Infer the team context from user text and hydrate the demo schedule.",
)
async def get_trip_details(
    context: RunContextWrapper[AirlineAgentChatContext], message: str
) -> str:
    store_id = schedule_repository.find_store_id(message)
    stores = schedule_repository.list_stores()
    store = next((item for item in stores if item["id"] == store_id), None)
    open_shifts = schedule_repository.list_store_shifts(store_id, status="open") if store_id else []
    staff = schedule_repository.list_store_staff(store_id) if store_id else []
    ctx = context.context.state
    ctx.scenario = "restaurant_sqlite"
    ctx.team_name = store["name"] if store else "餐饮门店"
    ctx.employee_name = staff[0]["name"] if staff else None
    ctx.schedule_date = open_shifts[0]["shift_date"] if open_shifts else None
    ctx.shift_id = open_shifts[0]["id"] if open_shifts else None
    ctx.shift_time = _format_shift_time(open_shifts[0]) if open_shifts else None
    ctx.role_name = open_shifts[0]["required_role"] if open_shifts else None
    return (
        f"已读取 {ctx.team_name} 的真实排班数据。"
        f"当前开放班次 {len(open_shifts)} 个，可安排伙伴 {len(staff)} 人。"
    )


@function_tool(
    name_override="get_staff_schedule",
    description_override="Get the assigned shift for a staff member on a given date.",
)
async def get_staff_schedule(
    context: RunContextWrapper[AirlineAgentChatContext],
    employee_name: str | None = None,
    schedule_date: str | None = None,
) -> str:
    await context.context.stream(ProgressUpdateEvent(text="Looking up schedule assignment..."))
    ctx_state = context.context.state
    name = employee_name or ctx_state.employee_name
    date = schedule_date or ctx_state.schedule_date
    assignments = schedule_repository.list_employee_assignments(name, date)
    if not assignments:
        return f"No assigned shift found for {name or 'this employee'} on {date or 'the requested date'}."
    match = assignments[0]
    ctx_state.employee_name = match.get("employee_name")
    ctx_state.team_name = match.get("store_name")
    ctx_state.schedule_date = match.get("shift_date")
    ctx_state.shift_id = match.get("shift_id")
    ctx_state.shift_time = _format_shift_time(match)
    ctx_state.role_name = match.get("required_role")
    weekly_hours = match.get("scheduled_hours", 0)
    guidance = ""
    if weekly_hours > MAX_WEEKLY_HOURS:
        guidance = f" Warning: weekly scheduled hours are {weekly_hours:.0f}, above guideline."
    lines = [
        (
            f"{item['employee_name']} 在 {item['store_name']} {item['shift_date']} "
            f"{item['template_name']}（{_format_shift_time(item)}）已排 {item['required_role']}。"
        )
        for item in assignments[:5]
    ]
    return (
        "\n".join(lines) + guidance
    )


@function_tool(
    name_override="get_available_shifts",
    description_override="Find open shifts for the requested team or date.",
)
async def get_available_shifts(
    context: RunContextWrapper[AirlineAgentChatContext],
    team_name: str | None = None,
    schedule_date: str | None = None,
) -> str:
    await context.context.stream(ProgressUpdateEvent(text="Searching for open shifts..."))
    ctx_state = context.context.state
    store_id = schedule_repository.find_store_id(team_name or ctx_state.team_name)
    final_shifts = schedule_repository.list_store_shifts(
        store_id,
        shift_date=schedule_date,
        status="open",
    )
    if not final_shifts:
        return "No open shifts found for the requested filters."
    ctx_state.team_name = final_shifts[0].get("store_name")
    ctx_state.schedule_date = final_shifts[0].get("shift_date")
    ctx_state.shift_id = final_shifts[0].get("id")
    ctx_state.shift_time = _format_shift_time(final_shifts[0])
    ctx_state.role_name = final_shifts[0].get("required_role")
    lines = [
        (
            f"{shift['id']} | {shift['store_name']} | {shift['shift_date']} | "
            f"{_format_shift_time(shift)} | {shift['required_role']} | "
            f"缺 {shift['open_count']} 人 | {shift.get('note') or '待补位'}"
        )
        for shift in final_shifts[:10]
    ]
    return "Open shifts:\n" + "\n".join(lines)


@function_tool(
    name_override="assign_shift",
    description_override="Assign an employee to an open shift.",
)
async def assign_shift(
    context: RunContextWrapper[AirlineAgentChatContext],
    employee_name: str,
    shift_id: str,
) -> str:
    await context.context.stream(ProgressUpdateEvent(text="Assigning shift..."))
    ctx_state = context.context.state
    scenario_key, schedule = active_itinerary(ctx_state)
    apply_itinerary_defaults(ctx_state, scenario_key=scenario_key)
    open_shifts = deepcopy(schedule.get("open_shifts", []))
    roster = deepcopy(schedule.get("roster", []))
    selection = next(
        (shift for shift in open_shifts if shift.get("shift_id", "").lower() == shift_id.lower()),
        None,
    )
    if not selection:
        return f"Shift {shift_id} is not currently open."
    risk_message = _assignment_risk_message(roster, employee_name, selection)
    if risk_message:
        return risk_message
    assigned = {
        **selection,
        "employee_name": employee_name,
        "status": "Assigned",
    }
    roster.append(assigned)
    remaining_open = [
        shift for shift in open_shifts if shift.get("shift_id", "").lower() != shift_id.lower()
    ]
    ctx_state.employee_name = employee_name
    ctx_state.team_name = assigned.get("team_name")
    ctx_state.schedule_date = assigned.get("schedule_date")
    ctx_state.shift_id = assigned.get("shift_id")
    ctx_state.shift_time = assigned.get("shift_time")
    ctx_state.role_name = assigned.get("role_name")
    ctx_state.roster = roster
    ctx_state.open_shifts = remaining_open
    ctx_state.schedule_note = f"Assigned {employee_name} to {shift_id}"
    projected_hours = _weekly_hours(roster, employee_name, assigned.get("team_name"))
    extra_note = ""
    if projected_hours >= 32:
        extra_note = f" Weekly scheduled hours now total {projected_hours:.0f}."
    return (
        f"Assigned {employee_name} to {shift_id} on {assigned.get('schedule_date')} "
        f"for {assigned.get('team_name')} ({assigned.get('shift_time')}).{extra_note}"
    )


@function_tool(
    name_override="remove_shift",
    description_override="Remove a scheduled shift assignment and mark it for backfill.",
)
async def remove_shift(
    context: RunContextWrapper[AirlineAgentChatContext],
    employee_name: str | None = None,
    shift_id: str | None = None,
) -> str:
    ctx_state = context.context.state
    scenario_key, schedule = active_itinerary(ctx_state)
    apply_itinerary_defaults(ctx_state, scenario_key=scenario_key)
    roster = deepcopy(ctx_state.roster or schedule.get("roster", []))
    match = next(
        (
            shift for shift in roster
            if (shift_id is None or shift.get("shift_id") == shift_id)
            and (employee_name is None or shift.get("employee_name") == employee_name)
        ),
        None,
    )
    if not match:
        return "No matching assigned shift was found to remove."
    roster = [shift for shift in roster if shift is not match]
    open_shifts = deepcopy(ctx_state.open_shifts or schedule.get("open_shifts", []))
    open_shifts.append(
        {
            "shift_id": match["shift_id"],
            "team_name": match["team_name"],
            "schedule_date": match["schedule_date"],
            "shift_time": match["shift_time"],
            "role_name": match["role_name"],
            "status": "Open",
            "note": f"Backfill opened after removing {match['employee_name']}",
        }
    )
    ctx_state.roster = roster
    ctx_state.open_shifts = open_shifts
    ctx_state.schedule_note = f"Removed {match['employee_name']} from {match['shift_id']}"
    return f"Removed {match['employee_name']} from {match['shift_id']} and reopened the shift for backfill."
