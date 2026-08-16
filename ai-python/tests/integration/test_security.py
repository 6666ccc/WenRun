import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from app.api.dependencies.runtime import ToolRuntimeContext
from app.graphs.hospital.checkpoint import protect_checkpointer
from app.graphs.hospital.graph import GraphDependencies, build_graph, graph_config
from app.models.chat import ChatRequest, ResumeRequest
from app.services.chat_service import ChatService, ChatServiceError
from app.services.java_tools.models import ToolFailure


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
        self.raise_timeout = False
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
        if self.raise_timeout:
            raise ToolFailure("JAVA_TOOL_TIMEOUT", "医院系统响应超时，请稍后重试。", True)
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


def chat_request(message: str, conversation_id: str) -> ChatRequest:
    return ChatRequest(message=message, conversationId=conversation_id)


def resume_request(conversation_id: str, interrupt_id: str, approved: bool) -> ResumeRequest:
    return ResumeRequest(
        conversationId=conversation_id,
        interruptId=interrupt_id,
        approved=approved,
    )


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
    return graph_config(conversation_id, token)


async def collect(stream):
    events = []
    async for event in stream:
        events.append(event)
    return events


def _deps(fake_java: FakeJava, intent="hospital"):
    return GraphDependencies(
        intent_agent=FixedIntentAgent(intent),
        chat_agent=FakeReplyAgent(),
        hospital_agent=FakeReplyAgent(),
        medical_agent=FakeReplyAgent(),
        clarify_agent=FakeReplyAgent(),
        hospital_retriever=FakeHospitalRetriever(),
        medical_retriever=lambda query: [],
        tools=fake_java,
    )


@pytest.fixture
def fake_java():
    return FakeJava()


@pytest.fixture
def checkpoint_spy():
    return protect_checkpointer(MemorySaver())


@pytest.fixture
def hospital_graph(fake_java, checkpoint_spy):
    return build_graph(_deps(fake_java), checkpointer=checkpoint_spy)


@pytest.fixture
def medical_graph():
    return build_graph(_deps(FakeJava(), intent="medical"))


@pytest.fixture
def chat_service(hospital_graph, checkpoint_spy, vector_memory):
    return ChatService(
        checkpointer=checkpoint_spy,
        vector_memory=vector_memory,
        graph=hospital_graph,
    )


@pytest.mark.asyncio
async def test_delegation_token_never_enters_checkpoint(chat_service, checkpoint_spy):
    stream = chat_service.stream_chat(
        chat_request("查询明天号源", "c-1"),
        ToolRuntimeContext("secret-delegation-token"),
    )
    async for event in stream:
        if event.type in {"done", "interrupt", "error"}:
            break
    aclose = getattr(stream, "aclose", None)
    if aclose:
        await aclose()
    assert "secret-delegation-token" not in checkpoint_spy.serialized_content()


@pytest.mark.asyncio
async def test_other_conversation_cannot_resume_interrupt(chat_service):
    interrupt_id = None
    stream = chat_service.stream_chat(
        chat_request("挂第一个号源", "c-1"),
        ToolRuntimeContext("read-token"),
    )
    async for event in stream:
        if event.type == "interrupt":
            interrupt_id = event.interrupt["interruptId"]
    assert interrupt_id
    with pytest.raises(ChatServiceError) as error:
        await collect(chat_service.resume_stream(
            resume_request("c-2", interrupt_id, True),
            ToolRuntimeContext("write-token"),
        ))
    assert error.value.code == "INTERRUPT_CONVERSATION_MISMATCH"


@pytest.mark.asyncio
async def test_tool_timeout_does_not_claim_success(hospital_graph, fake_java):
    fake_java.raise_timeout = True
    result = await hospital_graph.ainvoke(
        patient_input("查询明天内科号源"),
        config_for("c-1", "read-token"),
    )
    assert result["error"]["code"] == "JAVA_TOOL_TIMEOUT"
    assert "挂号成功" not in result["messages"][-1].content


@pytest.mark.asyncio
async def test_medical_answer_without_evidence_is_conservative(medical_graph):
    result = await medical_graph.ainvoke(
        patient_input("解释一种知识库中没有的疾病"),
        config_for("c-1", None),
    )
    assert result["sources"] == []
    assert "没有足够依据" in result["messages"][-1].content


@pytest.mark.asyncio
async def test_expired_interrupt_cannot_create_registration(chat_service, fake_java):
    with pytest.raises(ChatServiceError) as error:
        await collect(chat_service.resume_stream(
            resume_request("c-1", "expired-interrupt", True),
            ToolRuntimeContext("write-token"),
        ))
    assert error.value.code == "INTERRUPT_EXPIRED"
    assert fake_java.create_calls == []


@pytest.mark.asyncio
async def test_delete_conversation_removes_checkpoint_and_vector_memory(
    chat_service, checkpoint_spy, vector_memory,
):
    await vector_memory.save_memory("c-1", ["偏好上午就诊"])
    stream = chat_service.stream_chat(
        chat_request("查询明天号源", "c-1"),
        ToolRuntimeContext("read-token"),
    )
    async for event in stream:
        if event.type in {"done", "interrupt", "error"}:
            break
    await chat_service.delete_conversation("c-1")
    assert not checkpoint_spy.exists("c-1")
    assert await vector_memory.load_memory("c-1", "任意查询") == []
