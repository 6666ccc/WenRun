from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

from app.graphs.hospital.nodes import summarize as summarize_module


def _history(count: int) -> list:
    messages = []
    for index in range(count):
        messages.extend([
            HumanMessage(content=f"问题{index}", id=f"h{index}"),
            AIMessage(content=f"回答{index}", id=f"a{index}"),
        ])
    return messages


def test_summarize_node_skips_short_conversations():
    assert summarize_module.summarize_node({"messages": _history(3)}) == {}


def test_summarize_node_compresses_old_messages(monkeypatch):
    captured = {}

    class FakeModel:
        def invoke(self, messages):
            captured["messages"] = messages
            return AIMessage(content='''{
                "patient_self_reports":["症状：感冒"],
                "preferences":["科室：内科"],
                "verified_business_facts":[],
                "pending_tasks":["确认内科号源"],
                "superseded_items":[],
                "version":1
            }''')

    monkeypatch.setattr(summarize_module, "model", FakeModel())
    history = _history(7)
    result = summarize_module.summarize_node({"messages": history, "summary": "已有摘要"})
    reports = result["summary"]["patient_self_reports"]
    assert [item["text"] for item in reports] == ["已有摘要", "症状：感冒"]
    assert reports[1]["source"] == "user_statement"
    assert reports[1]["verification"] == "unverified"
    assert reports[1]["reported_at"]
    assert result["summary"]["pending_tasks"] == ["确认内科号源"]
    assert all(isinstance(item, RemoveMessage) for item in result["messages"])
    assert [item.id for item in result["messages"]] == [m.id for m in history[:-6]]
    assert "已有摘要" in captured["messages"][-1].content


def test_new_summary_fact_supersedes_old_value():
    existing = summarize_module.ConversationSummary(
        preferences=["回复长度：简短"], version=2
    )
    incoming = summarize_module.ConversationSummary(
        preferences=["回复长度：详细"], version=1
    )

    merged = summarize_module.merge_summary(existing, incoming)

    assert merged.preferences == ["回复长度：详细"]
    assert "回复长度：简短" in merged.superseded_items
    assert merged.version == 3


def test_summarize_node_does_not_break_turn_on_model_error(monkeypatch):
    class BrokenModel:
        def invoke(self, messages):
            raise RuntimeError("model down")

    monkeypatch.setattr(summarize_module, "model", BrokenModel())
    assert summarize_module.summarize_node({"messages": _history(7)}) == {}
