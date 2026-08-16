"""Shared retrieval adapter for hospital/medical nodes."""

from app.graphs.hospital.state import State
from app.rag.collections import KnowledgeBase


def retrieve_for_node(retriever, base: KnowledgeBase, state: State) -> list:
    query = last_user_text(state)
    if retriever is None:
        return []
    if callable(retriever):
        return list(retriever(query) or [])
    retrieve = getattr(retriever, "retrieve", None)
    if callable(retrieve):
        try:
            return list(retrieve(base, query) or [])
        except TypeError:
            return list(retrieve(query) or [])
    return []


def last_user_text(state: State) -> str:
    for message in reversed(list(state.get("messages") or [])):
        if _is_user(message):
            return _message_text(message)
    messages = list(state.get("messages") or [])
    return _message_text(messages[-1]) if messages else ""


def _is_user(message) -> bool:
    role = _message_role(message).lower()
    return role in {"user", "human"}


def _message_role(message) -> str:
    if isinstance(message, dict):
        return str(message.get("role") or message.get("type") or "")
    return str(getattr(message, "type", None) or getattr(message, "role", "") or "")


def _message_text(message) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")
