"""Build a bounded LangGraph input after an operational checkpoint miss."""

from collections.abc import Sequence
from typing import Protocol

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately

MAX_RECOVERY_TOKENS = 4_000


class RecoveryMessageLike(Protocol):
    id: int | None
    role: str
    content: str

    def model_copy(self, *, update: dict) -> "RecoveryMessageLike": ...


def build_rehydrated_messages(
    recovery_messages: Sequence[RecoveryMessageLike],
    current_message: str,
    *,
    max_tokens: int = MAX_RECOVERY_TOKENS,
) -> list[BaseMessage]:
    """Deduplicate and keep the newest authoritative messages inside a token budget."""

    current = HumanMessage(content=current_message)
    unique: list[RecoveryMessageLike] = []
    seen: set[tuple[object, ...]] = set()
    for item in recovery_messages:
        content = item.content.strip()
        if not content:
            continue
        identity = ("id", item.id) if item.id is not None else ("content", item.role, content)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(item.model_copy(update={"content": content}))

    kept_reversed: list[BaseMessage] = []
    for item in reversed(unique):
        message_type = HumanMessage if item.role == "user" else AIMessage
        candidate = message_type(content=item.content)
        chronological = [candidate, *reversed(kept_reversed), current]
        if count_tokens_approximately(chronological) > max_tokens:
            continue
        kept_reversed.append(candidate)

    return [*reversed(kept_reversed), current]
