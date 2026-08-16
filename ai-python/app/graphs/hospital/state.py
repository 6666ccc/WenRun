from typing import Literal

from langgraph.graph import MessagesState


class State(MessagesState):
    conversation_id: str
    user_id: int | None
    patient_id: int | None
    intent: Literal["chat", "hospital", "medical"] | None
    memory_enabled: bool
    task_plan: list[dict]
    tool_context: dict
    sources: list[dict]
    pending_action: dict | None
    error: dict | None
    retry_count: int
    needs_rewrite: bool
