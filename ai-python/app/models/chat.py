"""聊天接口收发的 JSON 格式，以及全图共用的模型实例。

Field 的 alias 是 Java 发来的 JSON 字段名，例如 conversationId；Python 内部
使用 conversation_id。Pydantic 会在路由函数运行前完成解析和字段校验。
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.budgeted import BudgetedChatModel

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# 图中的各个 Agent 复用同一模型配置；这里只创建客户端，不代表已发起聊天。
model = BudgetedChatModel(
    delegate=init_chat_model(
        model=os.environ["DASHSCOPE_CHAT_MODEL"],
        model_provider="openai",
        api_key=os.environ["DASHSCOPE_API_KEY"],
        base_url=os.environ["DASHSCOPE_BASE_URL"],
        temperature=0.2,
        max_retries=0,
        timeout=60,
    )
)


class ApiModel(BaseModel):
    """API 模型统一支持 conversationId 这类驼峰字段。"""

    model_config = ConfigDict(populate_by_name=True)


class UserContext(ApiModel):
    """Java 在请求体中附带的身份提示；最终以委托 JWT 验证出的身份为准。"""

    user_id: int | None = Field(default=None, alias="userId")
    operator_user_id: int | None = Field(default=None, alias="operatorUserId")
    patient_id: int | None = Field(default=None, alias="patientId")


class RecoveryMessage(ApiModel):
    """Java 权威消息存储提供的有限恢复窗口。"""

    id: int | None = None
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    client_request_id: str | None = Field(default=None, alias="clientRequestId")
    create_time: datetime | None = Field(default=None, alias="createTime")
    metadata_json: str | None = Field(default=None, alias="metadataJson")


class LongTermMemory(ApiModel):
    """Java 提供的、允许用于本轮回答的长期偏好记录。"""

    memory_id: str = Field(alias="memoryId", max_length=64)
    type: Literal[
        "communication_preference", "appointment_preference", "accessibility_need"
    ]
    content: str = Field(min_length=1, max_length=500)
    status: Literal["active"] = "active"
    update_time: datetime | None = Field(default=None, alias="updateTime")
    expire_time: datetime | None = Field(default=None, alias="expireTime")


class ChatRequest(ApiModel):
    """/stream 的请求体：用户消息、模式开关，以及可选的恢复资料。"""

    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message", mode="before")
    @classmethod
    def reject_oversized_message(cls, value: object) -> object:
        if isinstance(value, str) and len(value) > 2000:
            from app.observability.context_metrics import record_event

            record_event("oversizedUserMessageCount")
            raise ValueError("消息超过2000字，请缩短或分段发送")
        return value

    conversation_id: str = Field(alias="conversationId", min_length=1, max_length=64)
    memory_enabled: bool = Field(
        default=True, alias="memoryEnabled"
    )  # 是否尝试使用带检查点的图
    preferences_enabled: bool = Field(default=True, alias="preferencesEnabled")
    client_request_id: str | None = Field(
        default=None, alias="clientRequestId", max_length=64
    )
    current_message_id: int | None = Field(default=None, alias="currentMessageId")
    recovery_summary: dict | None = Field(default=None, alias="recoverySummary")
    recovery_upper_id: int = Field(default=0, alias="recoveryUpperId", ge=0)
    execution_id: str | None = Field(default=None, alias="executionId", max_length=64)
    fast_mode: bool = Field(default=False, alias="fastMode")  # 快速图只有公开搜索工具
    user_context: UserContext = Field(default_factory=UserContext, alias="userContext")
    recovery_messages: list[RecoveryMessage] = Field(
        # 检查点丢失时，Java 保存的最近消息可供有限恢复；不是本轮新消息。
        default_factory=list,
        alias="recoveryMessages",
        max_length=200,
    )
    long_term_memories: list[LongTermMemory] = Field(
        default_factory=list, alias="longTermMemories", max_length=20
    )


class ChatResumeRequest(ApiModel):
    """患者对确认卡片作出选择后，恢复被挂起的那一轮对话。"""

    conversation_id: str = Field(alias="conversationId", min_length=1, max_length=64)
    decision: Literal["approve", "reject"]
    client_request_id: str | None = Field(
        default=None, alias="clientRequestId", max_length=128
    )
    interrupt_id: str | None = Field(default=None, alias="interruptId", max_length=128)
    user_context: UserContext = Field(default_factory=UserContext, alias="userContext")

    @field_validator("interrupt_id", mode="before")
    @classmethod
    def empty_interrupt_id(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class ChatResponse(ApiModel):
    """普通 JSON 聊天响应。"""

    reply: str
    status: Literal["completed", "pending"] = "completed"
    conversation_id: str = Field(alias="conversationId")
    selected_agents: list[str] = Field(default_factory=list, alias="selectedAgents")
    sources: list[dict[str, Any]] = Field(default_factory=list)
