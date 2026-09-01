from typing import Literal

from langgraph.graph import MessagesState

AgentName = Literal["knowledge", "chat", "tools"]

"""节点，主要还是意图判断，以及后续的节点选择"""


class State(MessagesState):
    conversation_id: str  # 会话id
    patient_id: int | None  # 患者id
    delegated_token: str  # 仅当前请求内的 Java Tool 委托令牌；禁止加入持久化 checkpoint
    request_id: str | None  # Java/Python/Tool API 共用的追踪号
    selected_agents: list[AgentName]  # begin 节点从 IntentDecision 写入，可多选
    knowledge_reply: str | None  # 知识节点写入
    rag_sources: list[dict] | None  # RAG 命中的资料来源，供最终响应展示引用
    chat_reply: str | None  # 闲聊节点写入，用户闲聊
    tools_reply: str | None  # 工具节点写入，用户选择工具
    final_reply: str | None  # 汇总节点写入，最终回复
