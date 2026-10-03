"""会话记忆策略：回合字段重置、统一上下文窗口与历史压缩。"""

from langchain_core.messages import BaseMessage

from app.core.config import get_settings
from app.graphs.hospital.state import State
from app.graphs.hospital.tokens import estimate_tokens

RECENT_MESSAGE_WINDOW = 6
TURN_SCOPED_REPLY_FIELDS = (
    "task_plan",
    "knowledge_reply",
    "rag_sources",
    "chat_reply",
    "tools_reply",
    "final_reply",
)
SUMMARY_KEEP_MESSAGES = RECENT_MESSAGE_WINDOW


def reset_turn_fields() -> dict[str, None]:
    """清空上一轮节点产出，避免 checkpoint 恢复后串轮。"""

    return {field: None for field in TURN_SCOPED_REPLY_FIELDS}


def needs_summary(state: State) -> bool:
    """消息数量或估算 token 数超过阈值时，提示摘要节点压缩历史。"""
    messages = list(state.get("messages") or [])
    settings = get_settings()
    return (
        len(messages) > settings.summary_message_limit
        or estimate_tokens(messages) > settings.summary_trigger_tokens
    )


def split_for_summary(state: State) -> tuple[list[BaseMessage], list[BaseMessage]]:
    """分出要压缩的旧消息与仍需逐字保留的最近消息。"""
    messages = list(state.get("messages") or [])
    keep = get_settings().summary_keep_messages
    split = max(0, len(messages) - keep)
    return messages[:split], messages[split:]
