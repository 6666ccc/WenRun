import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt

from app.graphs.hospital import graphs
from app.graphs.hospital.tools.context import HospitalToolContext

CONTEXT = HospitalToolContext("delegated-token", "trace-1", writes_enabled=True)


def _install_stub_nodes(monkeypatch, *, agents, plan, interrupt_in_tool=False):
    """用可观测的桩节点替换真实节点，只验证图的编排行为。"""

    order: list[str] = []
    final_calls: list[dict] = []

    def begin_node(state):
        return {"selected_agents": agents, "task_plan": None}

    def plan_node(state):
        order.append("plan")
        return {"task_plan": plan}

    def knowledge_node(state):
        order.append("knowledge")
        return {"knowledge_reply": "呼吸内科"}

    def chat_node(state):
        order.append("chat")
        return {"chat_reply": "今天星期四"}

    def tool_node(state, runtime):
        order.append(f"tool:{state.get('knowledge_reply')}")
        if interrupt_in_tool:
            decision = interrupt({"kind": "registration_create", "prompt": "确认？", "detail": {}})
            order.append(f"tool-resumed:{decision}")
        return {"tools_reply": "已挂号"}

    def final_node(state):
        final_calls.append(dict(state))
        reply = " | ".join(
            text for text in (
                state.get("knowledge_reply"), state.get("chat_reply"), state.get("tools_reply")
            ) if text
        )
        return {"final_reply": reply, "messages": [AIMessage(content=reply)]}

    for name, node in {
        "begin_node": begin_node,
        "plan_node": plan_node,
        "knowledge_node": knowledge_node,
        "chat_node": chat_node,
        "tool_node": tool_node,
        "final_node": final_node,
    }.items():
        monkeypatch.setattr(graphs, name, node)
    monkeypatch.setattr(graphs, "summarize_node", lambda state: {})
    return order, final_calls


def _run(graph, text="x", config=None):
    return graph.invoke(
        {"messages": [HumanMessage(content=text)], "conversation_id": "c"},
        context=CONTEXT,
        config=config,
    )


def test_single_intent_skips_planner_and_runs_only_that_node(monkeypatch):
    order, final_calls = _install_stub_nodes(monkeypatch, agents=["chat"], plan=None)

    result = _run(graphs.build_graph())

    assert order == ["chat"]
    assert len(final_calls) == 1
    assert result["final_reply"] == "今天星期四"


def test_dependent_tool_waits_for_knowledge_and_final_runs_once(monkeypatch):
    plan = {"tasks": [
        {"agent": "knowledge", "goal": "k", "depends_on": []},
        {"agent": "chat", "goal": "c", "depends_on": []},
        {"agent": "tools", "goal": "t", "depends_on": ["knowledge"]},
    ]}
    order, final_calls = _install_stub_nodes(
        monkeypatch, agents=["knowledge", "chat", "tools"], plan=plan
    )

    result = _run(graphs.build_graph())

    assert order[0] == "plan"
    assert set(order[1:3]) == {"knowledge", "chat"}
    # tool_node 在 knowledge 之后才启动，并且已经拿到了知识助手的结论。
    assert order[3] == "tool:呼吸内科"
    assert len(final_calls) == 1
    assert result["final_reply"] == "呼吸内科 | 今天星期四 | 已挂号"


def test_independent_tasks_fan_out_in_parallel(monkeypatch):
    plan = {"tasks": [
        {"agent": "knowledge", "goal": "k", "depends_on": []},
        {"agent": "tools", "goal": "t", "depends_on": []},
    ]}
    order, final_calls = _install_stub_nodes(monkeypatch, agents=["knowledge", "tools"], plan=plan)

    _run(graphs.build_graph())

    # 并行分支里 tool_node 与 knowledge_node 同一步启动，看不到对方的结果。
    assert order[0] == "plan"
    assert set(order[1:]) == {"knowledge", "tool:None"}
    assert len(final_calls) == 1


def test_planner_failure_falls_back_to_parallel_dispatch(monkeypatch):
    order, final_calls = _install_stub_nodes(monkeypatch, agents=["knowledge", "tools"], plan=None)

    _run(graphs.build_graph())

    assert set(order[1:]) == {"knowledge", "tool:None"}
    assert len(final_calls) == 1


def test_interrupt_inside_dependent_tool_resumes_and_finalizes_once(monkeypatch):
    plan = {"tasks": [
        {"agent": "knowledge", "goal": "k", "depends_on": []},
        {"agent": "chat", "goal": "c", "depends_on": []},
        {"agent": "tools", "goal": "t", "depends_on": ["knowledge"]},
    ]}
    order, final_calls = _install_stub_nodes(
        monkeypatch, agents=["knowledge", "chat", "tools"], plan=plan, interrupt_in_tool=True
    )
    graph = graphs.build_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "t-interrupt"}}

    paused = _run(graph, config=config)
    snapshot = graph.get_state(config)

    assert paused.get("final_reply") is None
    assert len(snapshot.interrupts) == 1
    assert final_calls == []

    resumed = graph.invoke(
        Command(resume={snapshot.interrupts[0].id: "approve"}), context=CONTEXT, config=config
    )

    assert order[-2:] == ["tool:呼吸内科", "tool-resumed:approve"]
    assert len(final_calls) == 1
    assert resumed["final_reply"] == "呼吸内科 | 今天星期四 | 已挂号"
