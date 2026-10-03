"""Recover authoritative messages without using the model-input token budget."""

import json
from collections.abc import Sequence
from time import monotonic
from typing import Protocol

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.core.config import get_settings
from app.models.chat import RecoveryMessage
from app.observability.context_metrics import record_event
from app.services.java_tool_client import JavaToolClient, JavaToolClientError


class RecoveryMessageLike(Protocol):
    """恢复消息只需提供角色、内容和可选 ID，无需依赖具体模型类。"""

    id: int | None
    role: str
    content: str

    def model_copy(self, *, update: dict) -> "RecoveryMessageLike": ...


def build_rehydrated_messages(
    recovery_messages: Sequence[RecoveryMessageLike],
    current_message: str,
    *,
    max_tokens: int | None = None,
    current_message_id: int | None = None,
    client_request_id: str | None = None,
) -> list[BaseMessage]:
    """去重并优先保留较新的消息，最后附上本轮用户消息。"""

    current = HumanMessage(
        content=current_message,
        id=f"{client_request_id}:user"
        if client_request_id
        else (f"db:{current_message_id}" if current_message_id else None),
        additional_kwargs={"db_id": current_message_id},
    )
    unique: list[RecoveryMessageLike] = []
    seen: set[tuple[object, ...]] = set()
    for item in recovery_messages:
        content = item.content.strip()
        if not content:
            continue
        identity = (
            ("id", item.id) if item.id is not None else ("content", item.role, content)
        )
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(item.model_copy(update={"content": content}))

    recovered: list[BaseMessage] = []
    for item in unique:
        if current_message_id is not None and item.id == current_message_id:
            continue
        message_type = HumanMessage if item.role == "user" else AIMessage
        key = getattr(item, "client_request_id", None)
        try:
            metadata = json.loads(getattr(item, "metadata_json", None) or "{}")
        except (ValueError, TypeError):
            metadata = {}
        safe = isinstance(metadata, dict) and metadata.get("summarySafe") is True
        recovered.append(
            message_type(
                content=item.content,
                id=f"{key}:{item.role}"
                if key
                else (f"db:{item.id}" if item.id else None),
                additional_kwargs={
                    "db_id": item.id,
                    "summary_safe": safe,
                    "created_at": str(getattr(item, "create_time", None) or ""),
                },
            )
        )

    return [*recovered, current]


def fetch_recovery_messages(request, context) -> list[RecoveryMessage]:
    from app.observability.context_metrics import measure_context_operation

    with measure_context_operation("recoveryLatencyMs"):
        try:
            return _fetch_recovery_messages(request, context)
        except (JavaToolClientError, ValueError):
            record_event("incompleteRecoveryCount")
            raise


def _fetch_recovery_messages(request, context) -> list[RecoveryMessage]:
    """Read a fixed database snapshot in strictly increasing ID pages."""
    if not request.recovery_upper_id:
        return list(request.recovery_messages)
    settings = get_settings()
    record_event("recoveryCount.mysql_messages")
    if request.recovery_summary:
        record_event("recoveryCount.mysql_summary")
    started = monotonic()
    summary = request.recovery_summary or {}
    cursor = summary.get("last_message_id") or 0
    recovered = []
    client = JavaToolClient()
    while cursor < request.recovery_upper_id:
        if monotonic() - started > settings.recovery_timeout_seconds:
            raise JavaToolClientError("完整恢复超时，请稍后重试")
        page = client.recovery_page(
            context.delegated_token,
            context.request_id,
            conversation_id=request.conversation_id,
            after_id=cursor,
            upper_id=request.recovery_upper_id,
        )
        items = [RecoveryMessage.model_validate(item) for item in page["messages"]]
        for item in items:
            if item.id is None or not cursor < item.id <= request.recovery_upper_id:
                raise JavaToolClientError("恢复消息顺序无效，未完成恢复")
            cursor = item.id
            recovered.append(item)
        record_event("recoveryBatches")
        if len(recovered) > settings.recovery_max_messages:
            raise JavaToolClientError("会话过长，未完成完整恢复，请稍后重试")
        if not page.get("hasMore"):
            if cursor != request.recovery_upper_id:
                raise JavaToolClientError("恢复未到达数据库固定上界，未完成恢复")
            return recovered
        if not items:
            raise JavaToolClientError("恢复消息存在缺口，未完成恢复")
    return recovered
