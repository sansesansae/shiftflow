from __future__ import annotations as _annotations

import os


def _clean_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or default


# DeepSeek API 兼容 OpenAI chat/completions，默认先走轻量模型。
_DEFAULT_MODEL = "deepseek-v4-flash"

AGENT_MODEL = _clean_env("AIRLINE_AGENT_MODEL", _clean_env("OPENAI_MODEL", _DEFAULT_MODEL)) or _DEFAULT_MODEL
GUARDRAIL_MODEL = _clean_env("AIRLINE_GUARDRAIL_MODEL", AGENT_MODEL) or AGENT_MODEL
OPENAI_BASE_URL = _clean_env("OPENAI_BASE_URL")
OPENAI_API_KEY = _clean_env("OPENAI_API_KEY")
