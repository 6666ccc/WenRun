from typing import Literal

from langgraph.graph import MessagesState
from pydantic import BaseModel, ConfigDict, Field

AgentName = Literal["knowledge", "chat", "tools"]


class ConversationSummary(BaseModel):
    """Validated, source-aware conversation compression stored in checkpoints."""

    model_config = ConfigDict(extra="forbid")

    patient_self_reports: list[str] = Field(default_factory=list, max_length=20)
    preferences: list[str] = Field(default_factory=list, max_length=20)
    verified_business_facts: list[str] = Field(default_factory=list, max_length=20)
    pending_tasks: list[str] = Field(default_factory=list, max_length=20)
    superseded_items: list[str] = Field(default_factory=list, max_length=30)
    version: int = Field(default=1, ge=1)

"""节点，主要还是意图判断，以及后续的节点选择"""


class State(MessagesState):
    conversation_id: str  # 前端会话 ID；checkpointer key 还必须拼入已验证 user ID
    patient_id: int | None  # 患者id
    selected_agents: list[AgentName]  # begin 节点从 IntentDecision 写入，可多选
    intent_route: dict | None  # 级联层、分数、规则、升级原因与版本，供日志/评测追踪
    router_fallback: bool  # 所有分类层均失败时，chat_node 输出确定性澄清
    router_response: str | None  # 拒识或分类失败时的确定性患者提示
    knowledge_reply: str | None  # 知识节点写入
    rag_sources: list[dict] | None  # RAG 命中的资料来源，供最终响应展示引用
    chat_reply: str | None  # 闲聊节点写入，用户闲聊
    tools_reply: str | None  # 工具节点写入，用户选择工具
    final_reply: str | None  # 汇总节点写入，最终回复
    summary: ConversationSummary | dict | str | None  # 兼容旧 checkpoint 的字符串摘要
    long_term_memories: list[dict]  # Java 权威存储候选；Context Builder 最多选择 5 条
