from __future__ import annotations as _annotations

from agents import Agent, RunContextWrapper, handoff
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

from .context import AirlineAgentChatContext
from .demo_data import apply_itinerary_defaults
from .settings import AGENT_MODEL
from .tools import (
    assign_shift,
    faq_lookup_tool,
    get_available_shifts,
    get_staff_schedule,
    get_trip_details,
    remove_shift,
)

MODEL = AGENT_MODEL


def schedule_lookup_instructions(
    run_context: RunContextWrapper[AirlineAgentChatContext], agent: Agent[AirlineAgentChatContext]
) -> str:
    ctx = run_context.context.state
    return (
        f"{RECOMMENDED_PROMPT_PREFIX}\n"
        "You are the Schedule Lookup Agent. Help users check who is assigned and which shifts are open.\n"
        f"Current team: {ctx.team_name or '[unknown]'}, employee: {ctx.employee_name or '[unknown]'}, date: {ctx.schedule_date or '[unknown]'}.\n"
        "1. Use get_staff_schedule when the user asks about a specific person or date.\n"
        "2. Use get_available_shifts when they ask for open coverage, replacement options, or gaps.\n"
        "3. Answer clearly with the assigned shift, team, date, and time. If a change is needed, hand off to the Shift Change Agent."
    )


schedule_lookup_agent = Agent[AirlineAgentChatContext](
    name="Schedule Lookup Agent",
    model=MODEL,
    handoff_description="Checks assigned shifts and open scheduling gaps.",
    instructions=schedule_lookup_instructions,
    tools=[get_staff_schedule, get_available_shifts],
)


def shift_change_instructions(
    run_context: RunContextWrapper[AirlineAgentChatContext], agent: Agent[AirlineAgentChatContext]
) -> str:
    ctx = run_context.context.state
    return (
        f"{RECOMMENDED_PROMPT_PREFIX}\n"
        "You are the Shift Change Agent. Handle shift pickup, reassignment, and backfill workflows.\n"
        f"Current team: {ctx.team_name or '[unknown]'}, employee: {ctx.employee_name or '[unknown]'}, open shift: {ctx.shift_id or '[unknown]'}.\n"
        "1. If the user asks to fill or pick up a shift, use get_available_shifts first when needed, then assign_shift.\n"
        "2. If the user wants to remove or cancel an assignment, use remove_shift and explain that the shift has been reopened.\n"
        "3. Summarize exactly what changed, including employee, shift id, date, and team.\n"
        "4. If the user asks about policy, hand off to the Policy FAQ Agent."
    )


shift_change_agent = Agent[AirlineAgentChatContext](
    name="Shift Change Agent",
    model=MODEL,
    handoff_description="Assigns staff to open shifts and removes assignments when replanning is needed.",
    instructions=shift_change_instructions,
    tools=[get_available_shifts, assign_shift, remove_shift, get_staff_schedule],
)


policy_faq_agent = Agent[AirlineAgentChatContext](
    name="Policy FAQ Agent",
    model=MODEL,
    handoff_description="Answers scheduling rules about leave, swaps, night shifts, and overtime.",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
    You are the Policy FAQ Agent.
    1. Identify the scheduling policy question.
    2. Use faq_lookup_tool instead of relying on your own knowledge.
    3. Respond with a direct policy answer and offer to hand back to Schedule Lookup or Shift Change if an action is needed.
    """,
    tools=[faq_lookup_tool],
)


triage_agent = Agent[AirlineAgentChatContext](
    name="Scheduling Triage Agent",
    model=MODEL,
    handoff_description="Routes scheduling questions to lookup, shift change, or policy specialists.",
    instructions=(
        f"{RECOMMENDED_PROMPT_PREFIX} "
        "You are the scheduling triage agent. Route the user to the right specialist: "
        "Schedule Lookup for checking assignments or open shifts, Shift Change for assigning or removing shifts, "
        "and Policy FAQ for rules about leave, swaps, night shifts, or overtime. "
        "If context is missing, call get_trip_details once to hydrate the demo team context before handing off."
    ),
    tools=[get_trip_details],
    handoffs=[],
)


async def on_schedule_handoff(context: RunContextWrapper[AirlineAgentChatContext]) -> None:
    apply_itinerary_defaults(context.context.state)


triage_agent.handoffs = [
    handoff(agent=schedule_lookup_agent, on_handoff=on_schedule_handoff),
    handoff(agent=shift_change_agent, on_handoff=on_schedule_handoff),
    handoff(agent=policy_faq_agent, on_handoff=on_schedule_handoff),
]
schedule_lookup_agent.handoffs.extend([shift_change_agent, policy_faq_agent, triage_agent])
shift_change_agent.handoffs.extend([policy_faq_agent, schedule_lookup_agent, triage_agent])
policy_faq_agent.handoffs.extend([schedule_lookup_agent, shift_change_agent, triage_agent])
