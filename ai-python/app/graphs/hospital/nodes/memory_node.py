"""当前会话记忆：短期窗口淘汰内容写入向量记忆，读取时按 conversationId 过滤。"""

from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.services.memory.window import trim_messages

if TYPE_CHECKING:
    from app.graphs.hospital.graph import GraphDependencies
    from app.graphs.hospital.state import State


def load_memory(state: "State") -> dict:
    return {}


def save_memory(state: "State") -> dict:
    return {}


def build_load_memory_node(deps: "GraphDependencies"):
    def load_memory_node(state: "State") -> dict:
        if state.get("memory_enabled") is False:
            return {}
        memory = getattr(deps, "vector_memory", None)
        if memory is None:
            return {}
        conversation_id = state.get("conversation_id") or ""
        query = _last_user_text(state) or "会话"
        loader = getattr(memory, "load_memory_sync", None) or memory.load_memory
        facts = loader(conversation_id, query)
        if not facts:
            return {}
        return {
            "messages": [
                {"role": "system", "content": "已知会话事实：\n" + "\n".join(facts)}
            ]
        }

    return load_memory_node


def build_save_memory_node(deps: "GraphDependencies"):
    def save_memory_node(state: "State") -> dict:
        if state.get("memory_enabled") is False:
            return {}
        memory = getattr(deps, "vector_memory", None)
        if memory is None:
            return {}
        budget = get_settings().short_term_token_budget
        window = trim_messages(state.get("messages") or [], budget)
        facts = [text for text in (_message_text(item) for item in window.overflow) if text]
        if facts:
            saver = getattr(memory, "save_memory_sync", None) or memory.save_memory
            saver(state.get("conversation_id") or "", facts)
        return {}

    return save_memory_node


def _last_user_text(state) -> str:
    for message in reversed(list(state.get("messages") or [])):
        role = _message_role(message)
        if role in {"user", "human"}:
            return _message_text(message)
    return ""


def _message_role(message) -> str:
    if isinstance(message, dict):
        return str(message.get("role") or message.get("type") or "").lower()
    return str(getattr(message, "type", None) or getattr(message, "role", "") or "").lower()


def _message_text(message) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")
