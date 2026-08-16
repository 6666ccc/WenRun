from typing import Any, Literal

from pydantic import Field

from app.models.chat import ApiModel
from app.models.source import CitationSource, ToolSource


class ChatStreamEvent(ApiModel):
    type: Literal["status", "token", "citation", "interrupt", "done", "error"]
    content: str | None = None
    reply: str | None = None
    code: str | None = None
    message: str | None = None
    sources: list[CitationSource | ToolSource] | None = None
    interrupt: dict[str, Any] | None = None
    conversation_id: str | None = Field(None, alias="conversationId")
    status: Literal["completed", "pending"] | None = None
    intent: Literal["chat", "hospital", "medical"] | None = None
