import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from datetime import datetime

from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from app.graphs.hospital.nodes import tool as tool_node_module
from app.graphs.hospital.tools import departments as departments_module
from app.graphs.hospital.tools.context import CLINIC_TZ, HospitalToolContext
from app.services.java_tool_client import Department, JavaToolClientError

FROZEN_NOW = datetime(2026, 9, 1, 11, 15, tzinfo=CLINIC_TZ)
CONTEXT = HospitalToolContext("delegated-token", "trace-123", now=FROZEN_NOW)


def _tool_runtime(context: HospitalToolContext) -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=context,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="call-1",
        store=None,
    )


def _graph_runtime(context: HospitalToolContext) -> Runtime:
    return Runtime(context=context)


class FakeJavaToolClient:
    def list_departments(self, delegated_token, request_id):
        assert delegated_token == "delegated-token"
        assert request_id == "trace-123"
        return [Department(id=1, name="内科"), Department(id=2, name="儿科")]


def test_tool_node_skips_when_tools_not_selected():
    assert tool_node_module.tool_node(
        {"selected_agents": ["chat"]}, _graph_runtime(CONTEXT)
    ) == {}


def test_list_departments_reads_delegation_from_runtime_context(monkeypatch):
    monkeypatch.setattr(departments_module, "JavaToolClient", FakeJavaToolClient)

    runtime = _tool_runtime(CONTEXT)

    assert (
        departments_module.list_departments.func(runtime=runtime)
        == "当前可查询的科室：内科、儿科。"
    )


def test_list_departments_degrades_when_java_tool_api_fails(monkeypatch):
    class BrokenJavaToolClient:
        def __init__(self):
            raise JavaToolClientError("JAVA_TOOL_BASE_URL is not configured")

    monkeypatch.setattr(departments_module, "JavaToolClient", BrokenJavaToolClient)

    runtime = _tool_runtime(CONTEXT)

    assert (
        departments_module.list_departments.func(runtime=runtime)
        == "暂时无法查询医院业务信息，请稍后重试。"
    )


def test_every_hospital_tool_is_mounted_and_documented():
    mounted = {item.name for item in tool_node_module.HOSPITAL_TOOLS}

    assert mounted == {
        "list_departments",
        "list_doctors",
        "list_schedules",
        "list_my_registrations",
    }
    for name in mounted:
        assert name in tool_node_module.TOOL_SYSTEM_PROMPT


def test_tool_node_invokes_agent_with_request_scoped_context(monkeypatch):
    captured: dict = {}

    class FakeAgent:
        def invoke(self, payload, *, context):
            captured["messages"] = payload["messages"]
            captured["context"] = context
            return {"messages": [HumanMessage(content="当前可查询的科室：内科、儿科。")]}

    monkeypatch.setattr(tool_node_module, "agent", FakeAgent())
    history = [HumanMessage(content="有哪些科室？")]
    result = tool_node_module.tool_node(
        {
            "selected_agents": ["tools"],
            "conversation_id": "conversation-1",
            "messages": history,
        },
        _graph_runtime(CONTEXT),
    )

    assert result == {"tools_reply": "当前可查询的科室：内科、儿科。"}
    assert captured["messages"] == history
    assert captured["context"] == CONTEXT
    assert captured["context"].now.tzinfo == CLINIC_TZ


def test_tool_system_prompt_includes_beijing_clock():
    prompt = tool_node_module.build_tool_system_prompt(FROZEN_NOW)

    assert "当前时间：2026-09-01 星期二 11:15（北京时间）。" in prompt
    assert prompt.startswith(tool_node_module.TOOL_SYSTEM_PROMPT)


def test_tool_prompt_guides_registration_instead_of_flatly_refusing():
    prompt = tool_node_module.TOOL_SYSTEM_PROMPT

    # 旧的一刀切禁令会让被路由过来的挂号请求直接吃闭门羹。
    assert "不挂号、不取消挂号" not in prompt
    # 新行为：先查清号源与本人预约，再引导到挂号页面完成最后一步。
    assert "不直接提交挂号" in prompt
    assert "挂号页面" in prompt


def test_tool_node_returns_unavailable_when_delegated_token_missing():
    assert tool_node_module.tool_node(
        {
            "selected_agents": ["tools"],
            "messages": [HumanMessage(content="有哪些科室？")],
        },
        _graph_runtime(HospitalToolContext("", "trace-123", now=FROZEN_NOW)),
    ) == {"tools_reply": "业务查询服务暂不可用，请稍后重试。"}


def test_state_schema_never_carries_delegated_token():
    from app.graphs.hospital.state import State

    assert "delegated_token" not in State.__annotations__
    assert "request_id" not in State.__annotations__
