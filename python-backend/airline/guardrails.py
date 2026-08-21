from __future__ import annotations as _annotations

from agents import GuardrailFunctionOutput, RunContextWrapper, TResponseInputItem, input_guardrail


def _latest_text(input: str | list[TResponseInputItem]) -> str:
    if isinstance(input, str):
        return input
    parts: list[str] = []
    for item in input:
        if isinstance(item, dict):
            content = item.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and isinstance(block.get("text"), str):
                        parts.append(block["text"])
    return " ".join(parts)


@input_guardrail(name="Relevance Guardrail")
async def relevance_guardrail(
    context: RunContextWrapper[None], agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    text = _latest_text(input).lower()
    allowed_keywords = [
        "flight",
        "airline",
        "seat",
        "booking",
        "cancel",
        "rebook",
        "delay",
        "airport",
        "baggage",
        "bag",
        "wifi",
        "voucher",
        "refund",
        "compensation",
        "check-in",
        "boarding",
        "gate",
        "paris",
        "new york",
        "austin",
        "hello",
        "hi",
        "thanks",
        "ok",
    ]
    is_relevant = any(keyword in text for keyword in allowed_keywords) or len(text.strip()) <= 8
    return GuardrailFunctionOutput(
        output_info={
            "reasoning": "Keyword-based local relevance check.",
            "is_relevant": is_relevant,
        },
        tripwire_triggered=not is_relevant,
    )


@input_guardrail(name="Jailbreak Guardrail")
async def jailbreak_guardrail(
    context: RunContextWrapper[None], agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    text = _latest_text(input).lower()
    blocked_patterns = [
        "system prompt",
        "ignore previous",
        "ignore all previous",
        "developer message",
        "reveal prompt",
        "show hidden instructions",
        "drop table",
        "<script",
        "sudo ",
        "rm -rf",
    ]
    is_safe = not any(pattern in text for pattern in blocked_patterns)
    return GuardrailFunctionOutput(
        output_info={
            "reasoning": "Pattern-based local jailbreak check.",
            "is_safe": is_safe,
        },
        tripwire_triggered=not is_safe,
    )
