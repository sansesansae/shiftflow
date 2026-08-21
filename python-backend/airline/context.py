from __future__ import annotations as _annotations

from pydantic import BaseModel


class AirlineAgentContext(BaseModel):
    """Context for the scheduling assistant runtime."""

    employee_name: str | None = None
    team_name: str | None = None
    schedule_date: str | None = None
    shift_id: str | None = None
    shift_time: str | None = None
    role_name: str | None = None
    scenario: str | None = None
    roster: list[dict[str, str]] | None = None
    open_shifts: list[dict[str, str]] | None = None
    schedule_note: str | None = None
    policy_topic: str | None = None


class AirlineAgentChatContext:
    """
    Minimal runtime context for local FastAPI runs.
    Holds the persisted scheduling context in `state` and ignores UI stream events.
    """

    def __init__(self, state: AirlineAgentContext):
        self.state = state

    async def stream(self, _event: object) -> None:
        return None


def create_initial_context() -> AirlineAgentContext:
    return AirlineAgentContext()


def public_context(ctx: AirlineAgentContext) -> dict:
    data = ctx.model_dump()
    hidden_keys = {"roster", "open_shifts", "scenario"}
    for key in list(data.keys()):
        if key in hidden_keys:
            data.pop(key, None)
    return data
