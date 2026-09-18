import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.graphs.hospital.nodes import plan


class StubModel:
    def __init__(self, responses: list[AIMessage | Exception]):
        self.responses = responses
        self.calls: list[list] = []

    def invoke(self, messages):
        self.calls.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _state(agents, text="感冒了该看哪科，帮我挂明天那个科的号"):
    return {"selected_agents": agents, "messages": [HumanMessage(content=text)]}


def test_plan_node_skips_model_for_single_intent(monkeypatch):
    stub = StubModel([])
    monkeypatch.setattr(plan, "model", stub)

    assert plan.plan_node(_state(["chat"], "你好")) == {"task_plan": None}
    assert stub.calls == []


def test_plan_node_parses_goals_and_dependency(monkeypatch):
    stub = StubModel([AIMessage(content=(
        '{"tasks":[{"agent":"knowledge","goal":"感冒该看哪科","depends_on":[]},'
        '{"agent":"tools","goal":"挂明天对应科室的号","depends_on":["knowledge"]}]}'
    ))])
    monkeypatch.setattr(plan, "model", stub)

    result = plan.plan_node(_state(["knowledge", "tools"]))

    assert result == {"task_plan": {"tasks": [
        {"agent": "knowledge", "goal": "感冒该看哪科", "depends_on": []},
        {"agent": "tools", "goal": "挂明天对应科室的号", "depends_on": ["knowledge"]},
    ]}}
    assert len(stub.calls) == 1
    assert isinstance(stub.calls[0][0], SystemMessage)
    assert "knowledge, tools" in stub.calls[0][0].content
    # 提示词里的 JSON 示例必须原样保留，不能被 format 吃掉花括号。
    assert '{"tasks":[' in stub.calls[0][0].content


def test_plan_node_drops_dependencies_outside_the_allowlist(monkeypatch):
    stub = StubModel([AIMessage(content=(
        '{"tasks":[{"agent":"knowledge","goal":"k","depends_on":["tools"]},'
        '{"agent":"chat","goal":"c","depends_on":["knowledge"]},'
        '{"agent":"tools","goal":"t","depends_on":["chat"]}]}'
    ))])
    monkeypatch.setattr(plan, "model", stub)

    result = plan.plan_node(_state(["knowledge", "chat", "tools"]))

    assert [task["depends_on"] for task in result["task_plan"]["tasks"]] == [[], [], []]


def test_plan_node_fills_missing_agents_and_ignores_unselected_ones(monkeypatch):
    stub = StubModel([AIMessage(content=(
        '{"tasks":[{"agent":"tools","goal":"挂号","depends_on":["knowledge"]},'
        '{"agent":"chat","goal":"多余","depends_on":[]}]}'
    ))])
    monkeypatch.setattr(plan, "model", stub)

    result = plan.plan_node(_state(["knowledge", "tools"]))

    assert result["task_plan"]["tasks"] == [
        {"agent": "knowledge", "goal": "", "depends_on": []},
        {"agent": "tools", "goal": "挂号", "depends_on": ["knowledge"]},
    ]


def test_plan_node_repairs_invalid_json_once(monkeypatch):
    stub = StubModel([
        AIMessage(content="先查科室再挂号"),
        AIMessage(content=(
            '{"tasks":[{"agent":"knowledge","goal":"k","depends_on":[]},'
            '{"agent":"tools","goal":"t","depends_on":["knowledge"]}]}'
        )),
    ])
    monkeypatch.setattr(plan, "model", stub)

    result = plan.plan_node(_state(["knowledge", "tools"]))

    assert result["task_plan"]["tasks"][1]["depends_on"] == ["knowledge"]
    assert len(stub.calls) == 2
    assert "上一次无效输出如下" in stub.calls[1][0].content


def test_plan_node_degrades_to_parallel_when_model_fails(monkeypatch):
    stub = StubModel([RuntimeError("provider down")])
    monkeypatch.setattr(plan, "model", stub)

    result = plan.plan_node(_state(["knowledge", "tools"]))

    assert result == {"task_plan": plan.parallel_plan(["knowledge", "tools"])}
    assert all(not task["depends_on"] for task in result["task_plan"]["tasks"])


def test_plan_helpers_read_goal_dependency_and_ready_agents():
    state = {"task_plan": {"tasks": [
        {"agent": "knowledge", "goal": " 感冒该看哪科 ", "depends_on": []},
        {"agent": "chat", "goal": "", "depends_on": []},
        {"agent": "tools", "goal": "挂号", "depends_on": ["knowledge"]},
    ]}}

    assert plan.task_goal(state, "knowledge") == "感冒该看哪科"
    assert plan.task_goal(state, "chat") is None
    assert plan.depends_on(state, "tools", "knowledge") is True
    assert plan.depends_on(state, "knowledge", "tools") is False
    assert plan.ready_agents(state) == ["knowledge", "chat"]
    assert plan.ready_agents({"task_plan": None}) == []
