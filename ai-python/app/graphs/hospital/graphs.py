from app.graphs.hospital.nodes.begin import begin_node
from app.graphs.hospital.nodes.chat import chat_node
from app.graphs.hospital.nodes.final import final_node
from app.graphs.hospital.nodes.knowledge import knowledge_node
from app.graphs.hospital.nodes.summarize import summarize_node
from app.graphs.hospital.nodes.tool import tool_node
from app.graphs.hospital.state import State
from app.graphs.hospital.tools.context import HospitalToolContext
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


def _selected_reply_nodes(state: State) -> list[str]:
    """将互不依赖的已选 Agent 并行分发，避免多意图请求串行等待。"""

    selected = state.get("selected_agents") or []
    node_by_agent = {
        "knowledge": "knowledge_node",
        "chat": "chat_node",
        "tools": "tool_node",
    }
    return [node_by_agent[agent] for agent in selected if agent in node_by_agent]


def _workflow() -> StateGraph:
    workflow = StateGraph(State, context_schema=HospitalToolContext)
    workflow.add_node("begin_node", begin_node)
    workflow.add_node("knowledge_node", knowledge_node)
    workflow.add_node("chat_node", chat_node)
    workflow.add_node("tool_node", tool_node)
    workflow.add_node("final_node", final_node)
    workflow.add_node("summarize_node", summarize_node)

    workflow.add_edge(START, "begin_node")
    workflow.add_conditional_edges("begin_node", _selected_reply_nodes)
    workflow.add_edge("knowledge_node", "final_node")
    workflow.add_edge("chat_node", "final_node")
    workflow.add_edge("tool_node", "final_node")
    workflow.add_edge("final_node", "summarize_node")
    workflow.add_edge("summarize_node", END)
    return workflow


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """按需编译对话图。checkpointer 为 None 时得到无记忆实例。"""

    return _workflow().compile(checkpointer=checkpointer)


# langgraph.json 依赖该模块级实例；导入阶段不连接 Redis。
graph = build_graph()
