import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, ConfigDict, Field

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

model = init_chat_model(
    model=os.environ["DASHSCOPE_CHAT_MODEL"],
    model_provider="openai",
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url=os.environ["DASHSCOPE_BASE_URL"],
    temperature=0.2,
)


class ApiModel(BaseModel):
    """API 模型统一支持 conversationId 这类驼峰字段。"""

    model_config = ConfigDict(populate_by_name=True)


class UserContext(ApiModel):
    user_id: int | None = Field(default=None, alias="userId")
    patient_id: int | None = Field(default=None, alias="patientId")


class ChatRequest(ApiModel):
    """患者端聊天请求。"""

    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str = Field(alias="conversationId", min_length=1, max_length=64)
    memory_enabled: bool = Field(default=True, alias="memoryEnabled")
    fast_mode: bool = Field(default=False, alias="fastMode")
    user_context: UserContext = Field(default_factory=UserContext, alias="userContext")


class ChatResumeRequest(ApiModel):
    """患者对确认卡片作出选择后，恢复被挂起的那一轮对话。"""

    conversation_id: str = Field(alias="conversationId", min_length=1, max_length=64)
    decision: Literal["approve", "reject"]
    user_context: UserContext = Field(default_factory=UserContext, alias="userContext")


class ChatResponse(ApiModel):
    """普通 JSON 聊天响应。"""

    reply: str
    status: Literal["completed", "pending"] = "completed"
    conversation_id: str = Field(alias="conversationId")
    selected_agents: list[str] = Field(default_factory=list, alias="selectedAgents")
    sources: list[dict[str, Any]] = Field(default_factory=list)
