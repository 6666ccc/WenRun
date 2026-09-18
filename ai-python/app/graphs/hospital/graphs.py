from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.graphs.hospital.nodes.begin import begin_node
from app.graphs.hospital.nodes.chat import chat_node
from app.graphs.hospital.nodes.fast import fast_node
from app.graphs.hospital.nodes.final import final_node
from app.graphs.hospital.nodes.knowledge import knowledge_node
from app.graphs.hospital.nodes.plan import depends_on, plan_node, ready_agents
from app.graphs.hospital.nodes.summarize import summarize_node
from app.graphs.hospital.nodes.tool import tool_node
from app.graphs.hospital.state import AgentName, State
from app.graphs.hospital.tools.context import HospitalToolContext

NODE_BY_AGENT: dict[AgentName, str] = {
    "knowledge": "knowledge_node",
    "chat": "chat_node",
    "tools": "tool_node",
}
REPLY_NODES = frozenset(NODE_BY_AGENT.values())


def _nodes_for(agents: list[str]) -> list[str]:
    return [NODE_BY_AGENT[agent] for agent in agents if agent in NODE_BY_AGENT]


def _after_begin(state: State) -> list[str]:
    """单意图直达对应节点（零额外开销）；多意图先进 plan_node 拆子目标与依赖。"""

    selected = [agent for agent in (state.get("selected_agents") or []) if agent in NODE_BY_AGENT]
    if len(selected) >= 2:
        return ["plan_node"]
    return _nodes_for(selected) or ["chat_node"]


def _dispatch_ready(state: State) -> list[str]:
    """按计划并行启动所有无依赖的 Agent；有依赖的由上游节点完成后接力。"""

    ready = _nodes_for(ready_agents(state))
    if ready:
        return ready
    # 计划为空只会在 plan_node 出错时发生；退回旧行为，全部并行。
    return _nodes_for(state.get("selected_agents") or []) or ["final_node"]


def _after_knowledge(state: State) -> str:
    """tools 依赖 knowledge 结论（如“该看哪科就挂哪科”）时接力到 tool_node。"""

    if depends_on(state, "tools", "knowledge"):
        return "tool_node"
    return "final_node"


def _workflow() -> StateGraph:
    workflow = StateGraph(State, context_schema=HospitalToolContext)
    workflow.add_node("begin_node", begin_node)
    workflow.add_node("plan_node", plan_node)
    workflow.add_node("knowledge_node", knowledge_node)
    workflow.add_node("chat_node", chat_node)
    workflow.add_node("tool_node", tool_node)
    # defer=True：chat_node 与 knowledge→tool 接力链可能落在不同 superstep，
    # 汇总必须等所有分支都结束后只执行一次。
    workflow.add_node("final_node", final_node, defer=True)
    workflow.add_node("summarize_node", summarize_node)

    workflow.add_edge(START, "begin_node")
    workflow.add_conditional_edges("begin_node", _after_begin, ["plan_node", *sorted(REPLY_NODES)])
    workflow.add_conditional_edges("plan_node", _dispatch_ready, [*sorted(REPLY_NODES), "final_node"])
    workflow.add_conditional_edges("knowledge_node", _after_knowledge, ["tool_node", "final_node"])
    workflow.add_edge("chat_node", "final_node")
    workflow.add_edge("tool_node", "final_node")
    workflow.add_edge("final_node", "summarize_node")
    workflow.add_edge("summarize_node", END)
    return workflow


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """按需编译对话图。checkpointer 为 None 时得到无记忆实例。"""

    return _workflow().compile(checkpointer=checkpointer)


def _fast_workflow() -> StateGraph:
    """快速模式：单个全能节点直接作答，只保留摘要压缩。"""

    workflow = StateGraph(State, context_schema=HospitalToolContext)
    workflow.add_node("fast_node", fast_node)
    workflow.add_node("summarize_node", summarize_node)

    workflow.add_edge(START, "fast_node")
    workflow.add_edge("fast_node", "summarize_node")
    workflow.add_edge("summarize_node", END)
    return workflow


def build_fast_graph(checkpointer: BaseCheckpointSaver | None = None):
    """按需编译快速模式图。checkpointer 为 None 时得到无记忆实例。"""

    return _fast_workflow().compile(checkpointer=checkpointer)


# langgraph.json 依赖该模块级实例；导入阶段不连接 Redis。
graph = build_graph()
fast_graph = build_fast_graph()
