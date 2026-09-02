"""会话记忆策略：回合字段重置、统一上下文窗口与历史压缩。"""

from langchain_core.messages import BaseMessage, SystemMessage

from app.graphs.hospital.state import State

RECENT_MESSAGE_WINDOW = 6
TURN_SCOPED_REPLY_FIELDS = (
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
    return len(state.get("messages") or []) > SUMMARY_TRIGGER_MESSAGES


def split_for_summary(state: State) -> tuple[list[BaseMessage], list[BaseMessage]]:
    messages = list(state.get("messages") or [])
    return messages[:-SUMMARY_KEEP_MESSAGES], messages[-SUMMARY_KEEP_MESSAGES:]
