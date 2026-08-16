import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.api.dependencies.runtime import ToolRuntimeContext
from app.graphs.hospital.graph import GraphDependencies, build_graph, graph_config
from app.models.chat import ChatRequest, ResumeRequest
from app.services.chat_service import ChatService, ChatServiceError
from app.services.memory.vector import VectorMemory


class FixedIntentAgent:
    def __init__(self, intent):
        self.intent = intent

    def invoke(self, payload):
        from app.models.intent_result import IntentResult

        return {"structured_response": IntentResult(intent=self.intent)}


class FakeReplyAgent:
    def __init__(self, text="答复"):
        self.text = text
        self.calls = 0

    def invoke(self, payload):
        self.calls += 1
        return {"messages": [AIMessage(content=self.text)]}


class SpyRetriever:
    def __init__(self, chunks=None):
        self.calls = []
        self.chunks = chunks or []

    def __call__(self, query):
        self.calls.append(query)
        return list(self.chunks)


class FakeJava:
    def __init__(self):
        self.calls = []
        self.create_calls = []
        self.schedules = [
            {
                "id": 1,
                "staffName": "李医生",
                "deptName": "外科",
                "workDate": "2026-08-17",
                "timePeriod": "下午",
                "registerFee": 15,
            }
        ]

    def query_depts(self, **kwargs):
        self.calls.append("query_depts")
        return [{"id": 3, "deptName": "外科"}]

    def query_doctors(self, **kwargs):
        self.calls.append("query_doctors")
        return [{"id": 4, "name": "李医生"}]

    def query_schedules(self, **kwargs):
        self.calls.append("query_schedules")
        return list(self.schedules)

    def create_registration(self, **kwargs):
        self.create_calls.append(kwargs)
        return {"id": 88}


def _state(message: str, conversation_id="c-1") -> dict:
    return {
        "messages": [{"role": "user", "content": message}],
        "conversation_id": conversation_id,
        "user_id": 1,
        "patient_id": 10,
        "intent": None,
        "memory_enabled": True,
        "task_plan": [],
        "tool_context": {},
        "sources": [],
        "pending_action": None,
        "error": None,
        "retry_count": 0,
    }


def _graph(intent, hospital_retriever=None, medical_retriever=None, tools=None, medical_agent=None, checkpointer=None):
    return build_graph(
        GraphDependencies(
            intent_agent=FixedIntentAgent(intent),
            chat_agent=FakeReplyAgent("你好，我在。"),
            hospital_agent=FakeReplyAgent("外科在门诊楼三层。[S1]"),
            medical_agent=medical_agent or FakeReplyAgent("口腔溃疡多为轻度黏膜损伤。[S1]"),
            clarify_agent=FakeReplyAgent("请再说具体一些"),
            hospital_retriever=hospital_retriever,
            medical_retriever=medical_retriever,
            tools=tools,
        ),
        checkpointer=checkpointer,
    )


@pytest.mark.asyncio
async def test_chat_request_does_not_call_rag_or_tools():
    hospital = SpyRetriever([{"content": "不该用", "documentId": "h", "title": "h"}])
    medical = SpyRetriever([{"content": "不该用", "documentId": "m", "title": "m"}])
    tools = FakeJava()
    graph = _graph("chat", hospital, medical, tools)
    result = await graph.ainvoke(_state("最近有点累，想聊聊"), graph_config("c-1", "read-token"))
    assert hospital.calls == []
    assert medical.calls == []
    assert tools.calls == []
    assert tools.create_calls == []
    assert result["intent"] == "chat"


@pytest.mark.asyncio
async def test_hospital_location_includes_hospital_citation():
    retriever = SpyRetriever([{
        "content": "外科在门诊楼三层",
        "documentId": "doc-1",
        "title": "医院门诊服务指南",
        "page": 2,
    }])
    graph = _graph("hospital", retriever, None, FakeJava())
    result = await graph.ainvoke(_state("外科在哪里"), graph_config("c-1", "read-token"))
    assert any(item.get("documentId") == "doc-1" for item in result["sources"])
    assert any(item.get("kind") == "rag" for item in result["sources"])


@pytest.mark.asyncio
async def test_location_and_registration_query_combines_rag_and_tool_sources():
    retriever = SpyRetriever([{
        "content": "外科在门诊楼三层",
        "documentId": "doc-1",
        "title": "医院指南",
        "page": 2,
    }])
    tools = FakeJava()
    graph = _graph("hospital", retriever, None, tools)
    result = await graph.ainvoke(
        _state("外科在哪里，明天下午有哪些医生，帮我挂一个号"),
        graph_config("c-1", "read-token"),
    )
    assert any(item.get("kind") == "rag" for item in result["sources"])
    assert any(item.get("kind") == "tool" for item in result["sources"])
    assert result["__interrupt__"]
    assert tools.create_calls == []


@pytest.mark.asyncio
async def test_interrupt_does_not_create_registration():
    tools = FakeJava()
    graph = _graph("hospital", SpyRetriever(), None, tools, checkpointer=MemorySaver())
    result = await graph.ainvoke(_state("帮我挂一个号"), graph_config("c-1", "read-token"))
    assert result["__interrupt__"]
    assert tools.create_calls == []


@pytest.mark.asyncio
async def test_rejected_resume_does_not_write():
    tools = FakeJava()
    graph = _graph("hospital", SpyRetriever(), None, tools, checkpointer=MemorySaver())
    config = graph_config("c-1", "read-token")
    interrupted = await graph.ainvoke(_state("帮我挂一个号"), config)
    interrupt_id = interrupted["__interrupt__"][0].value["interruptId"]
    await graph.ainvoke(Command(resume={"interruptId": interrupt_id, "approved": False}), config)
    assert tools.create_calls == []


@pytest.mark.asyncio
async def test_approved_resume_rechecks_slot_and_creates_once():
    tools = FakeJava()
    graph = _graph("hospital", SpyRetriever(), None, tools, checkpointer=MemorySaver())
    config = graph_config("c-1", "read-token")
    interrupted = await graph.ainvoke(_state("帮我挂一个号"), config)
    interrupt_id = interrupted["__interrupt__"][0].value["interruptId"]
    await graph.ainvoke(
        Command(resume={"interruptId": interrupt_id, "approved": True}),
        graph_config("c-1", "write-token"),
    )
    assert len(tools.create_calls) == 1
    assert tools.calls.count("query_schedules") >= 2


@pytest.mark.asyncio
async def test_duplicate_resume_does_not_charge_again():
    tools = FakeJava()
    graph = _graph("hospital", SpyRetriever(), None, tools, checkpointer=MemorySaver())
    service = ChatService(graph=graph)
    interrupt_id = None
    async for event in service.stream_chat(
        ChatRequest(message="帮我挂一个号", conversationId="c-1"),
        ToolRuntimeContext("read-token"),
    ):
        if event.type == "interrupt":
            interrupt_id = event.interrupt["interruptId"]
    assert interrupt_id

    async def collect(request):
        events = []
        async for event in service.resume_stream(request, ToolRuntimeContext("write-token")):
            events.append(event)
        return events

    await collect(ResumeRequest(conversationId="c-1", interruptId=interrupt_id, approved=True))
    with pytest.raises(ChatServiceError) as error:
        await collect(ResumeRequest(conversationId="c-1", interruptId=interrupt_id, approved=True))
    assert error.value.code == "INTERRUPT_ALREADY_RESOLVED"
    assert len(tools.create_calls) == 1


@pytest.mark.asyncio
async def test_medical_ulcer_answer_includes_medical_citation():
    retriever = SpyRetriever([{
        "content": "口腔溃疡多为轻度黏膜损伤，注意口腔卫生。",
        "documentId": "med-1",
        "title": "口腔护理",
        "page": 3,
    }])
    graph = _graph("medical", None, retriever, None)
    result = await graph.ainvoke(_state("口腔溃疡怎么护理"), graph_config("c-1", None))
    assert any(item.get("documentId") == "med-1" for item in result["sources"])
    assert "口腔溃疡" in result["messages"][-1].content


@pytest.mark.asyncio
async def test_diagnosis_request_states_permission_boundary():
    graph = _graph("medical", None, SpyRetriever(), None)
    result = await graph.ainvoke(_state("请帮我诊断并开药"), graph_config("c-1", None))
    assert "没有诊断和开药" in result["messages"][-1].content


@pytest.mark.asyncio
async def test_new_conversation_cannot_recall_old_memory():
    memory = VectorMemory()
    await memory.save_memory("old-session", ["患者偏好上午就诊"])
    assert await memory.load_memory("old-session", "偏好") == ["患者偏好上午就诊"]
    assert await memory.load_memory("new-session", "偏好") == []
