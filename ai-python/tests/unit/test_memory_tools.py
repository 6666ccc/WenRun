from datetime import datetime
from typing import ClassVar

from langchain.tools import ToolRuntime

from app.graphs.hospital.tools import memory as memory_tools
from app.graphs.hospital.tools.context import CLINIC_TZ, HospitalToolContext
from app.services.java_tool_client import PatientMemory


def _runtime() -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=HospitalToolContext(
            "delegated", "trace", patient_id=12,
            conversation_id="conversation-1",
            writes_enabled=True,
            now=datetime(2026, 9, 13, tzinfo=CLINIC_TZ),
        ),
        config={},
        stream_writer=lambda _: None,
        tool_call_id="tool-1",
        store=None,
    )


class FakeClient:
    created: ClassVar[list] = []
    deleted: ClassVar[list] = []

    def create_memory(self, token, request_id, **kwargs):
        self.created.append(kwargs)
        return PatientMemory("memory-1", kwargs["memory_type"], kwargs["content"], "active", 1)

    def list_memories(self, token, request_id):
        return [PatientMemory("memory-1", "communication_preference", "回复简短", "active", 1)]

    def delete_memory(self, token, request_id, *, memory_id):
        self.deleted.append(memory_id)


def test_remember_preference_requires_confirmation(monkeypatch):
    FakeClient.created.clear()
    monkeypatch.setattr(memory_tools, "JavaToolClient", FakeClient)
    monkeypatch.setattr(memory_tools, "interrupt", lambda payload: "reject")

    result = memory_tools.remember_preference.func(
        memory_type="communication_preference", content="回复简短", runtime=_runtime()
    )

    assert "没有保存" in result
    assert FakeClient.created == []


def test_confirmed_memory_uses_conversation_source(monkeypatch):
    FakeClient.created.clear()
    monkeypatch.setattr(memory_tools, "JavaToolClient", FakeClient)
    monkeypatch.setattr(memory_tools, "interrupt", lambda payload: "approve")

    memory_tools.remember_preference.func(
        memory_type="appointment_preference", content="偏好上午号源", runtime=_runtime()
    )

    assert FakeClient.created == [{
        "memory_type": "appointment_preference",
        "content": "偏好上午号源",
        "source_conversation_id": "conversation-1",
    }]


def test_forget_only_deletes_an_owned_active_memory_after_confirmation(monkeypatch):
    FakeClient.deleted.clear()
    monkeypatch.setattr(memory_tools, "JavaToolClient", FakeClient)
    monkeypatch.setattr(memory_tools, "interrupt", lambda payload: "approve")

    result = memory_tools.forget_preference.func(memory_id="memory-1", runtime=_runtime())

    assert "已忘掉" in result
    assert FakeClient.deleted == ["memory-1"]
