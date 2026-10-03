from langchain_core.messages import HumanMessage

from app.graphs.hospital import memory


def test_reset_turn_fields_clears_every_node_output():
    assert memory.reset_turn_fields() == {
        "task_plan": None,
        "knowledge_reply": None,
        "rag_sources": None,
        "chat_reply": None,
        "tools_reply": None,
        "final_reply": None,
    }


def test_summary_threshold_and_split():
    short = [HumanMessage(content=str(index)) for index in range(12)]
    long = [HumanMessage(content=str(index)) for index in range(14)]
    assert memory.needs_summary({"messages": short}) is False
    assert memory.needs_summary({"messages": long}) is True
    dropped, kept = memory.split_for_summary({"messages": long})
    assert dropped == long[:-6]
    assert kept == long[-6:]
