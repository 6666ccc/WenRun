import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

from app.graphs.hospital.nodes import summarize as mod
from app.graphs.hospital.tools.context import HospitalToolContext


def history(count=7):
    return [
        kind(
            content=f"问题{index}",
            id=f"r{index // 2}:{'user' if index % 2 == 0 else 'assistant'}",
            additional_kwargs={"db_id": index + 1},
        )
        for index, kind in enumerate([HumanMessage, AIMessage] * count)
    ]


def state():
    return {"messages": history(), "conversation_id": "c", "durable_summary_version": 0}


def runtime():
    return SimpleNamespace(
        context=HospitalToolContext("token", conversation_id="c", execution_id="owner")
    )


@pytest.fixture
def fixture(monkeypatch):
    events = []
    result = {
        "schema_version": 2,
        "patient_self_reports": [{"text": "问题0", "source_message_id": 1}],
        "pending_tasks": ["选择挂号时段"],
        "superseded_items": [],
        "version": 1,
    }

    class Model:
        def invoke(self, messages):
            events.append("model")
            return AIMessage(content=json.dumps(result, ensure_ascii=False))

    class Client:
        def commit_conversation_summary(self, *args, **kwargs):
            events.append(("commit", kwargs))
            return {"version": 1, "lastMessageId": 8}

    monkeypatch.setattr(mod, "model", Model())
    monkeypatch.setattr(mod, "JavaToolClient", Client)
    return events, result


def test_only_acknowledged_prefix_is_removed(fixture):
    events, _ = fixture
    update = mod.summarize_node(state(), runtime())
    assert events[0] == "model"
    assert events[1][1]["covered_ids"] == list(range(1, 9))
    assert all(isinstance(item, RemoveMessage) for item in update["messages"])
    assert len(update["messages"]) == 8
    assert update["summary"]["last_message_id"] == 8
    assert update["summary"]["patient_self_reports"][0]["verification"] == "unverified"


def test_failed_or_lost_ack_keeps_every_raw_message(fixture, monkeypatch):
    class FailedClient:
        def commit_conversation_summary(self, *args, **kwargs):
            raise TimeoutError("ACK lost")

    monkeypatch.setattr(mod, "JavaToolClient", FailedClient)
    original = state()
    assert mod.summarize_node(original, runtime()) == {}
    assert len(original["messages"]) == 14


def test_no_execution_owner_cannot_compact(fixture):
    assert mod.summarize_node(state()) == {}
    assert fixture[0] == []


def test_commit_conflict_requests_recovery_without_removing_history(
    fixture, monkeypatch
):
    from app.services.java_tool_client import JavaToolBusinessError

    class ConflictingClient:
        def commit_conversation_summary(self, *args, **kwargs):
            raise JavaToolBusinessError("version conflict", code=409)

    monkeypatch.setattr(mod, "JavaToolClient", ConflictingClient)
    original = state()
    assert mod.summarize_node(original, runtime()) == {"requires_recovery": True}
    assert len(original["messages"]) == 14


@pytest.mark.parametrize("field", ["verified_business_facts", "preferences"])
def test_removed_fields_reject_candidate(fixture, field):
    fixture[1][field] = []
    assert mod.summarize_node(state(), runtime()) == {}
    assert len(fixture[0]) == 1


def test_tool_or_assistant_excerpt_cannot_become_self_report(fixture):
    fixture[1]["patient_self_reports"] = [{"text": "问题1", "source_message_id": 2}]
    assert mod.summarize_node(state(), runtime()) == {}
    assert len(fixture[0]) == 1


def test_same_prefix_unresolved_items_are_not_implicitly_replaced():
    existing = mod.ConversationSummary(
        pending_tasks=["挂号：内科", "挂号：儿科"], version=2
    )
    incoming = mod.ConversationSummary(pending_tasks=["挂号：口腔科"])
    merged = mod.merge_summary(existing, incoming)
    assert merged.pending_tasks == ["挂号：内科", "挂号：儿科", "挂号：口腔科"]
    assert merged.version == 3


def test_saved_items_beyond_old_twenty_item_cap_survive():
    existing = mod.ConversationSummary(pending_tasks=[f"待追问{i}" for i in range(40)])
    merged = mod.merge_summary(
        existing, mod.ConversationSummary(pending_tasks=["新追问"])
    )
    assert len(merged.pending_tasks) == 41


def test_incomplete_summary_is_a_failure_not_empty_success():
    assert mod._parse_summary("{}") is None
    assert mod._parse_summary('{"pending_tasks":[]}') is None


def test_clinical_assistant_text_never_enters_compression_prompt():
    transcript = mod._transcript(
        [
            HumanMessage(content="查询体重", additional_kwargs={"db_id": 1}),
            AIMessage(content="档案摘录：体重62公斤", additional_kwargs={"db_id": 2}),
        ]
    )
    assert "62公斤" not in transcript
    assert "查询体重" in transcript
