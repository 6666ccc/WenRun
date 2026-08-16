from dataclasses import dataclass
from typing import Any


@dataclass
class WindowResult:
    kept: list[Any]
    overflow: list[Any]


def estimate_tokens(message) -> int:
    text = _message_text(message)
    return max(1, (len(text) + 1) // 2)


def trim_messages(messages, token_budget: int) -> WindowResult:
    kept: list[Any] = []
    overflow: list[Any] = []
    used = 0
    for message in reversed(list(messages or [])):
        cost = estimate_tokens(message)
        if not kept or used + cost <= token_budget:
            kept.append(message)
            used += cost
        else:
            overflow.append(message)
    kept.reverse()
    overflow.reverse()
    return WindowResult(kept=kept, overflow=overflow)


def _message_text(message) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")
