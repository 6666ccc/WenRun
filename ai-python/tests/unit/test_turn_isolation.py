import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

import json

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.graphs.hospital import graphs
from app.graphs.hospital.nodes import begin as begin_module
from app.graphs.hospital.nodes import chat as chat_module
from app.graphs.hospital.nodes import final as final_module
from app.graphs.hospital.nodes import knowledge as knowledge_module
from app.graphs.hospital.tools.context import HospitalToolContext

CONTEXT = HospitalToolContext("delegated-token", "trace-1")
CONFIG = {"configurable": {"thread_id": "isolation-thread"}}


class _StubRetriever:
    def invoke(self, query):
        return [Document(page_content="多休息多喝水", metadata={"source_name": "院内资料", "page": 1})]


class _StubAgent:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    def invoke(self, payload, **kwargs):
        self.calls += 1
        return {"messages": [AIMessage(content=self.reply)]}


class _StreamingStubModel:
    def __init__(self, reply):
        self.reply = reply

    def stream(self, messages):
        yield AIMessage(content=self.reply)


def _stub_nodes(monkeypatch, intents):
    """按回合顺序返回意图，并把所有 LLM 出口替换成确定性桩。"""

    pending = iter(intents)
    monkeypatch.setattr(
        begin_module,
        "_classify",
        lambda messages: json.dumps({"selected_agents": next(pending)}),
    )
    monkeypatch.setattr(knowledge_module, "get_hospital_retriever", lambda: _StubRetriever())
    monkeypatch.setattr(
        knowledge_module,
        "model",
        _StreamingStubModel("感冒建议：多喝水"),
    )
    chat_model = _StreamingStubModel("不客气，还有需要随时说。")
    monkeypatch.setattr(chat_module, "model", chat_model)
    final_agent = _StubAgent("这不该被调用")
    return chat_model, final_agent


def test_second_turn_does_not_reuse_previous_turn_replies(monkeypatch):
    _, final_agent = _stub_nodes(monkeypatch, [["knowledge"], ["chat"]])
    graph = graphs.build_graph(checkpointer=InMemorySaver())

    first = graph.invoke(
        {"messages": [HumanMessage(content="感冒吃什么药")], "conversation_id": "isolation-thread"},
        context=CONTEXT,
        config=CONFIG,
    )
    assert first["final_reply"] == "感冒建议：多喝水"

    second = graph.invoke(
        {"messages": [HumanMessage(content="谢谢你啊")], "conversation_id": "isolation-thread"},
        context=CONTEXT,
        config=CONFIG,
    )

    # 上一轮的知识回复必须已被清零，否则 final_node 会把两条一起汇总。
    assert second["knowledge_reply"] is None
    assert second["rag_sources"] is None
    assert second["final_reply"] == "不客气，还有需要随时说。"
    assert final_agent.calls == 0


def test_checkpointer_accumulates_history_across_turns(monkeypatch):
    _stub_nodes(monkeypatch, [["chat"], ["chat"]])
    graph = graphs.build_graph(checkpointer=InMemorySaver())

    graph.invoke(
        {"messages": [HumanMessage(content="你好")], "conversation_id": "isolation-thread"},
        context=CONTEXT,
        config=CONFIG,
    )
    second = graph.invoke(
        {"messages": [HumanMessage(content="谢谢")], "conversation_id": "isolation-thread"},
        context=CONTEXT,
        config=CONFIG,
    )

    contents = [message.content for message in second["messages"]]
    assert contents == ["你好", "不客气，还有需要随时说。", "谢谢", "不客气，还有需要随时说。"]


def test_long_conversation_gets_compressed_into_summary(monkeypatch):
    _stub_nodes(monkeypatch, [["chat"]] * 8)
    monkeypatch.setattr(
        "app.graphs.hospital.nodes.summarize.model",
        type("M", (), {"invoke": staticmethod(lambda messages: AIMessage(content="患者多次寒暄致谢。"))})(),
    )
    graph = graphs.build_graph(checkpointer=InMemorySaver())

    state = {}
    for index in range(8):
        state = graph.invoke(
            {
                "messages": [HumanMessage(content=f"你好{index}")],
                "conversation_id": "isolation-thread",
            },
            context=CONTEXT,
            config=CONFIG,
        )

    assert state["summary"] == "患者多次寒暄致谢。"
    # 压缩后消息数被压回窗口附近，不再随轮次线性增长。
    assert len(state["messages"]) <= 8
