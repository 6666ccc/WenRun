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
            return AIMessage(content="患者先后咨询了感冒用药与内科号源。")

    monkeypatch.setattr(summarize_module, "model", FakeModel())
    history = _history(7)
    result = summarize_module.summarize_node({"messages": history, "summary": "已有摘要"})
    assert result["summary"].startswith("患者")
    assert all(isinstance(item, RemoveMessage) for item in result["messages"])
    assert [item.id for item in result["messages"]] == [m.id for m in history[:-6]]
    assert "已有摘要" in captured["messages"][-1].content


def test_summarize_node_does_not_break_turn_on_model_error(monkeypatch):
    class BrokenModel:
        def invoke(self, messages):
            raise RuntimeError("model down")

    monkeypatch.setattr(summarize_module, "model", BrokenModel())
    assert summarize_module.summarize_node({"messages": _history(7)}) == {}
