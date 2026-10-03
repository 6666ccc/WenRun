from datetime import datetime
from types import SimpleNamespace

from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.graphs.hospital.state import State
from app.graphs.hospital.tools import memory as mod
from app.graphs.hospital.tools.context import CLINIC_TZ, HospitalToolContext
from app.services.java_tool_client import PatientMemory


def test_resume_reuses_displayed_version_and_expiry_without_refetch(monkeypatch):
    reads, writes = [], []

    class Client:
        def list_memories(self, *args):
            reads.append(True)
            return [
                PatientMemory(
                    "m", "communication_preference", "回复简短", "active", len(reads)
                )
            ]

        def update_memory(self, *args, **kwargs):
            writes.append(kwargs)

    monkeypatch.setattr(mod, "JavaToolClient", Client)

    def node(state, runtime):
        tool_runtime = ToolRuntime(
            state=state,
            context=runtime.context,
            config={},
            stream_writer=lambda _: None,
            tool_call_id="call",
            store=None,
        )
        return {
            "tools_reply": mod.remember_preference.func(
                "communication_preference", "回复详细", tool_runtime, 7
            )
        }

    builder = StateGraph(State, context_schema=HospitalToolContext)
    builder.add_node("save", node)
    builder.add_edge(START, "save")
    builder.add_edge("save", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "test"}}
    context = HospitalToolContext(
        "delegated",
        patient_id=2,
        conversation_id="c",
        writes_enabled=True,
        now=datetime(2026, 10, 3, 12, tzinfo=CLINIC_TZ),
    )
    graph.invoke(
        {"messages": [HumanMessage(content="请记住回复详细")]}, config, context=context
    )
    card = graph.get_state(config).interrupts[0].value
    assert card["kind"] == "memory_update"
    assert card["detail"]["oldContent"] == "回复简短"
    assert not writes
    graph.invoke(Command(resume="approve"), config, context=context)
    assert len(reads) == 1
    assert writes[0]["expected_version"] == 1
    assert writes[0]["expire_time"] == card["detail"]["expireTime"]


def test_trusted_interrupt_snapshot_wins_if_shallow_saver_reexecutes_task(monkeypatch):
    from app.graphs.hospital.confirmation import resume_command

    original = {
        "target": {"memory_id": "m", "version": 2, "content": "回复简短"},
        "expireTime": "2026-10-10T12:00:00",
        "content": "回复详细",
        "memoryType": "communication_preference",
        "patientId": 2,
    }
    command, _, _ = resume_command(
        "approve",
        "i",
        [{"id": "i", "kind": "memory_update", "_preference_snapshot": original}],
    )
    reads = {
        **original,
        "target": {"memory_id": "m", "version": 3, "content": "回复长篇"},
        "expireTime": "2026-10-10T13:00:00",
    }
    monkeypatch.setattr(
        mod, "_preference_snapshot", lambda *args: SimpleNamespace(result=lambda: reads)
    )
    monkeypatch.setattr(mod, "interrupt", lambda value: command.resume["i"])
    writes = []

    class Client:
        def update_memory(self, *args, **kwargs):
            writes.append(kwargs)

    monkeypatch.setattr(mod, "JavaToolClient", Client)
    runtime = ToolRuntime(
        state={"messages": [HumanMessage(content="请记住回复详细")]},
        context=HospitalToolContext("token", patient_id=2, writes_enabled=True),
        config={},
        stream_writer=lambda _: None,
        tool_call_id="call",
        store=None,
    )
    mod.remember_preference.func("communication_preference", "回复详细", runtime, 7)
    assert writes[0]["expected_version"] == 2
    assert writes[0]["expire_time"] == original["expireTime"]


def test_legacy_preference_card_without_snapshot_cannot_be_approved():
    from app.graphs.hospital.confirmation import resume_command

    command, code, _ = resume_command(
        "approve", "i", [{"id": "i", "kind": "memory_create"}]
    )
    assert command is None
    assert code == "AI_RESUME_STALE"
