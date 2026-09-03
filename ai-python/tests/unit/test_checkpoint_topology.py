import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.graphs.hospital import graphs
from app.graphs.hospital.nodes import begin as begin_module
from app.graphs.hospital.nodes import chat as chat_module
from app.graphs.hospital.nodes.summarize import summarize_node
from app.graphs.hospital.state import State
from app.graphs.hospital.tools.context import HospitalToolContext

CONTEXT = HospitalToolContext("delegated-token", "trace-1")
CONFIG = {"configurable": {"thread_id": "cross-topology"}}


class _StreamingStubModel:
    def __init__(self, reply):
        self.reply = reply

    def stream(self, messages):
        yield AIMessage(content=self.reply)


def _spike_fast_graph(checkpointer):
    """与计划中的快速模式同形：单个根节点写 final_reply，后接共用的 summarize_node。"""

    def spike_node(state: State) -> dict:
        reply = "快速模式回复"
        return {"final_reply": reply, "messages": [AIMessage(content=reply)]}

    workflow = StateGraph(State, context_schema=HospitalToolContext)
    workflow.add_node("fast_node", spike_node)
    workflow.add_node("summarize_node", summarize_node)
    workflow.add_edge(START, "fast_node")
    workflow.add_edge("fast_node", "summarize_node")
    workflow.add_edge("summarize_node", END)
    return workflow.compile(checkpointer=checkpointer)


def test_fast_and_normal_graphs_resume_the_same_thread(monkeypatch):
    monkeypatch.setattr(
        begin_module, "_classify", lambda messages: '{"selected_agents":["chat"]}'
    )
    monkeypatch.setattr(chat_module, "model", _StreamingStubModel("正常模式回复"))

    saver = InMemorySaver()
    normal = graphs.build_graph(checkpointer=saver)
    fast = _spike_fast_graph(saver)

    normal.invoke(
        {"messages": [HumanMessage(content="你好")], "conversation_id": "cross-topology"},
        context=CONTEXT,
        config=CONFIG,
    )
    fast_state = fast.invoke(
        {"messages": [HumanMessage(content="继续")], "conversation_id": "cross-topology"},
        context=CONTEXT,
        config=CONFIG,
    )
    final_state = normal.invoke(
        {"messages": [HumanMessage(content="再问一句")], "conversation_id": "cross-topology"},
        context=CONTEXT,
        config=CONFIG,
    )

    # 快速模式必须能看到正常模式写下的历史。
    assert [message.content for message in fast_state["messages"]] == [
        "你好",
        "正常模式回复",
        "继续",
        "快速模式回复",
    ]
    # 切回正常模式后，快速模式那一轮也必须还在。
    assert [message.content for message in final_state["messages"]] == [
        "你好",
        "正常模式回复",
        "继续",
        "快速模式回复",
        "再问一句",
        "正常模式回复",
    ]
