"""会话记忆策略：回合字段重置、统一上下文窗口与历史压缩。"""

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.messages.utils import count_tokens_approximately

from app.core.config import get_settings
from app.graphs.hospital.context_builder import build_context
from app.graphs.hospital.state import State

RECENT_MESSAGE_WINDOW = 6
TURN_SCOPED_REPLY_FIELDS = (
    "task_plan",
    "knowledge_reply",
    "rag_sources",
    "chat_reply",
    "tools_reply",
    "final_reply",
)
SUMMARY_TRIGGER_MESSAGES = 12
SUMMARY_KEEP_MESSAGES = RECENT_MESSAGE_WINDOW


def reset_turn_fields() -> dict[str, None]:
    """清空上一轮节点产出，避免 checkpoint 恢复后串轮。"""

    return {field: None for field in TURN_SCOPED_REPLY_FIELDS}


def recent_messages(
    state: State, limit: int = RECENT_MESSAGE_WINDOW
) -> list[BaseMessage]:
    """所有节点唯一的上下文窗口；有历史摘要时拼在最前面。"""

    tail = list(state.get("messages") or [])[-limit:]
    summary = state.get("summary")
    if isinstance(summary, str) and summary.strip():
        return [SystemMessage(content=f"【历史摘要】\n{summary.strip()}"), *tail]
    return tail


def needs_summary(state: State) -> bool:
    messages = list(state.get("messages") or [])
    settings = get_settings()
    return (
        len(messages) > settings.summary_message_limit
        or count_tokens_approximately(messages) > settings.summary_trigger_tokens
    )


def split_for_summary(state: State) -> tuple[list[BaseMessage], list[BaseMessage]]:
    messages = list(state.get("messages") or [])
    kept = build_context({"messages": messages}, purpose="chat")[-SUMMARY_KEEP_MESSAGES:]
    keep_ids = {id(message) for message in kept}
    dropped = [message for message in messages if id(message) not in keep_ids]
    return dropped, kept
