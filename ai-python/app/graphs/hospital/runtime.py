"""生产图依赖：LLM、隔离检索、Java Tool 与会话记忆。测试通过注入 GraphDependencies 绕过。"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.config import Settings
from app.core.llm import create_chat_model
from app.graphs.hospital.graph import GraphDependencies
from app.graphs.hospital.prompts.chat import CHAT_SYSTEM_PROMPT
from app.graphs.hospital.prompts.hospital import HOSPITAL_SYSTEM_PROMPT
from app.graphs.hospital.prompts.intent import INTENT_SYSTEM_PROMPT
from app.graphs.hospital.prompts.medical import MEDICAL_SYSTEM_PROMPT
from app.models.intent_result import IntentResult
from app.rag.collections import KnowledgeBase
from app.rag.rag import retrieve
from app.services.java_tools.client import JavaToolsClient
from app.services.java_tools.facade import JavaHospitalTools


CLARIFY_SYSTEM_PROMPT = (
    "你是意图澄清助手。用简短问句确认患者是想闲聊、了解医院信息或办事，还是咨询健康科普。"
    "不要回答业务问题，也不要给出诊断。"
)


def build_production_dependencies(settings: Settings, vector_memory=None) -> GraphDependencies:
    llm = create_chat_model(settings)
    return GraphDependencies(
        intent_agent=StructuredIntentAgent(llm),
        chat_agent=PromptedAgent(llm, CHAT_SYSTEM_PROMPT),
        hospital_agent=PromptedAgent(llm, HOSPITAL_SYSTEM_PROMPT),
        medical_agent=PromptedAgent(llm, MEDICAL_SYSTEM_PROMPT),
        clarify_agent=PromptedAgent(llm, CLARIFY_SYSTEM_PROMPT),
        hospital_retriever=_retriever(KnowledgeBase.HOSPITAL),
        medical_retriever=_retriever(KnowledgeBase.MEDICAL),
        tools=JavaHospitalTools(JavaToolsClient(settings.java_base_url)),
        vector_memory=vector_memory,
    )


def _retriever(base: KnowledgeBase):
    def retrieve_query(query: str):
        return retrieve(base, query)

    return retrieve_query


def to_lc_messages(messages) -> list:
    converted = []
    for message in messages or []:
        role = _role(message)
        content = _content(message)
        if role in {"user", "human"}:
            converted.append(HumanMessage(content=content))
        elif role in {"assistant", "ai"}:
            converted.append(AIMessage(content=content))
        else:
            converted.append(SystemMessage(content=content))
    return converted


class StructuredIntentAgent:
    def __init__(self, llm):
        self._llm = llm.with_structured_output(IntentResult)
        self._system = INTENT_SYSTEM_PROMPT

    def invoke(self, payload):
        messages = [SystemMessage(content=self._system), *to_lc_messages(payload.get("messages"))]
        return self._llm.invoke(messages)


class PromptedAgent:
    def __init__(self, llm, system_prompt: str):
        self._llm = llm
        self._system = system_prompt

    def invoke(self, payload):
        messages = [SystemMessage(content=self._system), *to_lc_messages(payload.get("messages"))]
        return self._llm.invoke(messages)


def _role(message) -> str:
    if isinstance(message, dict):
        return str(message.get("role") or message.get("type") or "").lower()
    return str(getattr(message, "type", None) or getattr(message, "role", "") or "").lower()


def _content(message) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")
