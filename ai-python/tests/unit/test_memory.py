from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.graphs.hospital import memory


def test_reset_turn_fields_clears_every_node_output():
    assert memory.reset_turn_fields() == {
        "task_plan": None, "knowledge_reply": None, "rag_sources": None,
        "chat_reply": None, "tools_reply": None, "final_reply": None,
    }


def test_recent_messages_keeps_tail_and_prepends_summary():
    history = [HumanMessage(content=str(index)) for index in range(10)]
    result = memory.recent_messages({"messages": history, "summary": "旧症状"})
    assert isinstance(result[0], SystemMessage)
    assert "旧症状" in result[0].content
    assert result[1:] == history[-6:]


def test_recent_messages_handles_empty_and_limit():
    assert memory.recent_messages({}) == []
    history = [HumanMessage(content="q"), AIMessage(content="a")]
    assert memory.recent_messages({"messages": history}, limit=1) == [history[-1]]


def test_recent_messages_ignores_blank_summary():
    history = [HumanMessage(content="q")]

    assert memory.recent_messages({"messages": history, "summary": "   "}) == history



def test_summary_threshold_and_split():
    short = [HumanMessage(content=str(index)) for index in range(12)]
    long = [HumanMessage(content=str(index)) for index in range(14)]
    assert memory.needs_summary({"messages": short}) is False
    assert memory.needs_summary({"messages": long}) is True
    dropped, kept = memory.split_for_summary({"messages": long})
    assert dropped == long[:-6]
    assert kept == long[-6:]
