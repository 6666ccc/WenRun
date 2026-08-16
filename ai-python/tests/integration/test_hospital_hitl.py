import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver


class FixedIntentAgent:
    def __init__(self, intent="hospital"):
        self.intent = intent

    def invoke(self, payload):
        from app.models.intent_result import IntentResult

        return {"structured_response": IntentResult(intent=self.intent)}


class FakeReplyAgent:
    def invoke(self, payload):
        return {"messages": [AIMessage(content="医院答复")]}


class FakeJava:
    def __init__(self):
        self.create_calls = []
        self.schedule_kwargs = []
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
        return [{"id": 3, "deptName": "外科"}]

    def query_doctors(self, **kwargs):
        return [{"id": 4, "name": "李医生"}]

    def query_schedules(self, **kwargs):
        self.schedule_kwargs.append(kwargs)
        return list(self.schedules)

    def create_registration(self, **kwargs):
        self.create_calls.append(kwargs)
        return {"id": 88}


class FakeHospitalRetriever:
    def __call__(self, query):
        return [
            {
                "content": "外科在门诊楼三层",
                "documentId": "doc-1",
                "title": "医院指南",
                "page": 2,
            }
        ]


def patient_input(text: str, conversation_id: str = "c-1") -> dict:
    return {
        "messages": [{"role": "user", "content": text}],
        "conversation_id": conversation_id,
        "user_id": 1,
        "patient_id": 10,
        "intent": None,
        "memory_enabled": False,
        "task_plan": [],
        "tool_context": {},
        "sources": [],
        "pending_action": None,
        "error": None,
        "retry_count": 0,
    }


def config_for(conversation_id: str, token: str | None):
    from app.graphs.hospital.graph import graph_config

    return graph_config(conversation_id, token)


def _deps(fake_java: FakeJava):
    from app.graphs.hospital.graph import GraphDependencies

    return GraphDependencies(
        intent_agent=FixedIntentAgent(),
        chat_agent=FakeReplyAgent(),
        hospital_agent=FakeReplyAgent(),
        medical_agent=FakeReplyAgent(),
        clarify_agent=FakeReplyAgent(),
        hospital_retriever=FakeHospitalRetriever(),
        tools=fake_java,
    )


def _graph(fake_java: FakeJava):
    from app.graphs.hospital.graph import build_graph

    return build_graph(_deps(fake_java), checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_hospital_agent_combines_rag_and_schedule_tool():
    fake_java = FakeJava()
    graph = _graph(fake_java)
    result = await graph.ainvoke(
        patient_input("外科在哪里，明天下午有哪些医生"),
        config_for("c-1", "read-token"),
    )
    assert any(s.get("kind") == "rag" for s in result["sources"])
    assert any(s.get("kind") == "tool" for s in result["sources"])
    assert fake_java.schedule_kwargs
    assert fake_java.schedule_kwargs[-1].get("dept_id") == 3
    assert fake_java.schedule_kwargs[-1].get("work_date")


@pytest.mark.asyncio
async def test_multiple_slots_ask_patient_to_choose():
    fake_java = FakeJava()
    fake_java.schedules = [
        {**fake_java.schedules[0], "id": 1, "staffName": "李医生"},
        {**fake_java.schedules[0], "id": 2, "staffName": "王医生"},
    ]
    graph = _graph(fake_java)
    result = await graph.ainvoke(
        patient_input("帮我挂号"),
        config_for("c-1", "read-token"),
    )
    assert not result.get("__interrupt__")
    assert fake_java.create_calls == []
    assert "选择" in result["messages"][-1].content


@pytest.mark.asyncio
async def test_registration_stops_at_interrupt():
    fake_java = FakeJava()
    graph = _graph(fake_java)
    result = await graph.ainvoke(
        patient_input("挂第一个号源"),
        config_for("c-1", "read-token"),
    )
    assert result["__interrupt__"]
    assert fake_java.create_calls == []


@pytest.mark.asyncio
async def test_rejected_resume_does_not_create_registration():
    from langgraph.types import Command

    fake_java = FakeJava()
    graph = _graph(fake_java)
    config = config_for("c-1", "read-token")
    interrupted = await graph.ainvoke(patient_input("挂第一个号源"), config)
    interrupt_id = interrupted["__interrupt__"][0].value["interruptId"]
    result = await graph.ainvoke(
        Command(resume={"interruptId": interrupt_id, "approved": False}),
        config_for("c-1", "read-token"),
    )
    assert fake_java.create_calls == []
    assert "取消" in result["messages"][-1].content


@pytest.mark.asyncio
async def test_approved_resume_creates_registration_once():
    from langgraph.types import Command

    fake_java = FakeJava()
    graph = _graph(fake_java)
    config = config_for("c-1", "read-token")
    interrupted = await graph.ainvoke(patient_input("挂第一个号源"), config)
    interrupt_id = interrupted["__interrupt__"][0].value["interruptId"]
    await graph.ainvoke(
        Command(resume={"interruptId": interrupt_id, "approved": True}),
        config_for("c-1", "write-token"),
    )
    assert len(fake_java.create_calls) == 1
    assert fake_java.create_calls[0]["token"] == "write-token"


@pytest.mark.asyncio
async def test_duplicate_resume_is_rejected():
    from app.api.dependencies.runtime import ToolRuntimeContext
    from app.models.chat import ResumeRequest
    from app.services.chat_service import ChatService, ChatServiceError

    fake_java = FakeJava()
    graph = _graph(fake_java)
    service = ChatService(graph=graph)
    stream = service.stream_chat(
        _chat_request("挂第一个号源", "c-1"),
        ToolRuntimeContext("read-token"),
    )
    interrupt_id = None
    async for event in stream:
        if event.type == "interrupt":
            interrupt_id = event.interrupt["interruptId"]
    assert interrupt_id

    async def collect(request):
        events = []
        agen = service.resume_stream(request, ToolRuntimeContext("write-token"))
        async for event in agen:
            events.append(event)
        return events

    first = await collect(ResumeRequest(
        conversation_id="c-1",
        interrupt_id=interrupt_id,
        approved=True,
    ))
    assert any(event.type == "done" for event in first)
    assert len(fake_java.create_calls) == 1

    with pytest.raises(ChatServiceError) as error:
        await collect(ResumeRequest(
            conversation_id="c-1",
            interrupt_id=interrupt_id,
            approved=True,
        ))
    assert error.value.code == "INTERRUPT_ALREADY_RESOLVED"
    assert len(fake_java.create_calls) == 1


@pytest.mark.asyncio
async def test_stream_emits_status_before_interrupt():
    from app.api.dependencies.runtime import ToolRuntimeContext
    from app.services.chat_service import ChatService

    fake_java = FakeJava()
    graph = _graph(fake_java)
    service = ChatService(graph=graph)
    events = []
    async for event in service.stream_chat(
        _chat_request("挂第一个号源", "c-1"),
        ToolRuntimeContext("read-token"),
    ):
        events.append(event)
    types = [event.type for event in events]
    assert "status" in types
    assert types[-1] == "interrupt"


def _chat_request(message: str, conversation_id: str):
    from app.models.chat import ChatRequest

    return ChatRequest(message=message, conversationId=conversation_id)
