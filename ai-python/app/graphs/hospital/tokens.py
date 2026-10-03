"""Conservative, deterministic estimates; not a provider tokenizer."""

import json
import math
from collections.abc import Iterable

from langchain_core.messages import BaseMessage


def _text_tokens(text: str) -> int:
    cjk = sum(
        0x2E80 <= ord(char) <= 0x9FFF
        or 0xAC00 <= ord(char) <= 0xD7AF
        or ord(char) >= 0x1F000
        for char in text
    )
    return cjk + math.ceil((len(text) - cjk) / 4)


def estimate_tokens(value, *, tools=None) -> int:
    """Include message envelopes, tool calls and schemas in the same estimate."""
    if isinstance(value, str):
        total = _text_tokens(value)
    elif isinstance(value, BaseMessage):
        content = value.content
        total = 8 + estimate_tokens(content)
        calls = getattr(value, "tool_calls", None)
        if calls:
            total += estimate_tokens(calls)
    elif isinstance(value, dict):
        total = _text_tokens(json.dumps(value, ensure_ascii=False, default=str))
    elif isinstance(value, Iterable):
        total = sum(estimate_tokens(item) for item in value)
    else:
        total = _text_tokens(str(value))
    return total + (estimate_tokens(tools) + 8 if tools else 0)
