from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class UserContext(ApiModel):
    user_id: int | None = Field(None, alias="userId")
    patient_id: int | None = Field(None, alias="patientId")


class ChatRequest(ApiModel):
    message: str = Field(min_length=1)
    conversation_id: str = Field(alias="conversationId", min_length=1)
    memory_enabled: bool = Field(True, alias="memoryEnabled")
    user_context: UserContext = Field(default_factory=UserContext, alias="userContext")


class ResumeRequest(ApiModel):
    conversation_id: str = Field(alias="conversationId", min_length=1)
    interrupt_id: str = Field(alias="interruptId", min_length=1)
    approved: bool
    params: dict[str, Any] | None = None


class ChatResponse(ApiModel):
    reply: str | None = None
    status: Literal["completed", "pending"]
    conversation_id: str = Field(alias="conversationId")
    intent: Literal["chat", "hospital", "medical"] | None = None
    interrupts: list[dict[str, Any]] = Field(default_factory=list)