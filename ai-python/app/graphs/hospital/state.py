from typing import Literal

from langgraph.graph import MessagesState
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.graphs.hospital.sensitive import cleaned_memory_text

AgentName = Literal["knowledge", "chat", "tools"]


class PatientSelfReport(BaseModel):
    """患者自述。只能来自原话，不能升级成已验证临床事实。"""

    model_config = ConfigDict(extra="ignore")

    text: str = Field(min_length=1, max_length=500)
    reported_at: str | None = None
    source: Literal["user_statement"] = "user_statement"
    verification: Literal["unverified"] = "unverified"

    @model_validator(mode="before")
    @classmethod
    def coerce_statement(cls, value: object) -> object:
        if isinstance(value, str):
            return {"text": cleaned_memory_text(value) or "已省略"}
        if isinstance(value, dict):
            raw = value.get("text", value.get("content", ""))
            reported = value.get("reported_at", value.get("reportedAt"))
            text = cleaned_memory_text(str(raw)) if raw is not None else None
            return {
                "text": text or "已省略",
                "reported_at": reported if isinstance(reported, str) and reported.strip() else None,
                "source": "user_statement",
                "verification": "unverified",
            }
        return value


class ConversationSummary(BaseModel):
    """Validated, source-aware conversation compression stored in checkpoints."""

    model_config = ConfigDict(extra="forbid")

    patient_self_reports: list[PatientSelfReport] = Field(default_factory=list, max_length=20)
    preferences: list[str] = Field(default_factory=list, max_length=20)
    verified_business_facts: list[str] = Field(default_factory=list, max_length=20)
    pending_tasks: list[str] = Field(default_factory=list, max_length=20)
    superseded_items: list[str] = Field(default_factory=list, max_length=30)
    version: int = Field(default=1, ge=1)

    @field_validator("patient_self_reports", mode="before")
    @classmethod
    def coerce_reports(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        kept: list[dict] = []
        for item in value:
            try:
                report = PatientSelfReport.model_validate(item)
            except ValidationError:
                continue
            if report.text == "已省略":
                continue
            kept.append(report.model_dump())
        return kept

    @field_validator(
        "preferences",
        "verified_business_facts",
        "pending_tasks",
        "superseded_items",
        mode="before",
    )
    @classmethod
    def clean_lines(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            text = cleaned_memory_text(item)
            if text is not None:
                cleaned.append(text)
        return cleaned

"""节点，主要还是意图判断，以及后续的节点选择"""


class State(MessagesState):
    conversation_id: str  # 前端会话 ID；checkpointer key 还必须拼入已验证 user ID
    patient_id: int | None  # 患者id
    selected_agents: list[AgentName]  # begin 节点从 IntentDecision 写入，可多选
    intent_route: dict | None  # 级联层、分数、规则、升级原因与版本，供日志/评测追踪
    # 多意图时由 plan_node 写入：{"tasks":[{"agent","goal","depends_on":[...]}]}
    # 单意图或规划失败时为 None，各节点退化为“整句原话 + 并行”的旧行为。
    task_plan: dict | None
    router_fallback: bool  # 所有分类层均失败时，chat_node 输出确定性澄清
    router_response: str | None  # 拒识或分类失败时的确定性患者提示
    knowledge_reply: str | None  # 知识节点写入
    rag_sources: list[dict] | None  # RAG 命中的资料来源，供最终响应展示引用
    chat_reply: str | None  # 闲聊节点写入，用户闲聊
    tools_reply: str | None  # 工具节点写入，用户选择工具
    final_reply: str | None  # 汇总节点写入，最终回复
    summary: ConversationSummary | dict | str | None  # 兼容旧 checkpoint 的字符串摘要
    long_term_memories: list[dict]  # Java 权威存储候选；Context Builder 最多选择 5 条
