import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from datetime import datetime

from langchain_core.messages import AIMessageChunk, HumanMessage
from langgraph.runtime import Runtime

from app.graphs.hospital.nodes import fast as fast_mod
from app.graphs.hospital.tools.context import CLINIC_TZ, HospitalToolContext

FROZEN_NOW = datetime(2026, 9, 1, 11, 15, tzinfo=CLINIC_TZ)
CONTEXT = HospitalToolContext("delegated-token", "trace-123", now=FROZEN_NOW)


def _graph_runtime(context: HospitalToolContext) -> Runtime:
    return Runtime(context=context)


class _ScriptedModel:
    """按脚本逐轮返回分片。每个脚本项是一轮 stream 要吐的 AIMessageChunk 列表。"""

    def __init__(self, turns):
        self.turns = list(turns)
        self.bound_tools = None
        self.seen_messages = []

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def stream(self, messages):
        self.seen_messages.append(list(messages))
        for chunk in self.turns.pop(0):
            yield chunk


def _text(content):
    return AIMessageChunk(content=content)


def _tool_call(name, args, call_id):
    return AIMessageChunk(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


def test_fast_node_answers_without_tools(monkeypatch):
    scripted = _ScriptedModel([[_text("你好，"), _text("我在。")]])
    monkeypatch.setattr(fast_mod, "model", scripted)

    result = fast_mod.fast_node(
        {"messages": [HumanMessage(content="你好")], "conversation_id": "c1"}
    )

    assert result["final_reply"] == "你好，我在。"
    assert result["rag_sources"] == []
    assert result["messages"][0].content == "你好，我在。"
    # 必须清空上一轮的节点产出，避免切模式后串轮。
    assert result["knowledge_reply"] is None
    assert result["chat_reply"] is None
    assert result["tools_reply"] is None
    # 快速图没有 begin_node，必须显式清空 checkpoint 里残留的 selected_agents。
    assert result["selected_agents"] == []
    # 只挂联网检索，绝不挂院内 RAG 或业务写/查工具。
    assert [tool.name for tool in scripted.bound_tools] == ["web_search"]


def test_fast_node_uses_web_search_and_leaves_rag_sources_empty(monkeypatch):
    scripted = _ScriptedModel(
        [
            [_tool_call("web_search", {"query": "感冒 用药"}, "call-1")],
            [_text("公开资料建议多休息。")],
        ]
    )
    monkeypatch.setattr(fast_mod, "model", scripted)
    monkeypatch.setattr(
        fast_mod, "web_search", _StubTool("web_search", "网页片段：多休息")
    )

    result = fast_mod.fast_node(
        {"messages": [HumanMessage(content="感冒吃什么药")], "conversation_id": "c1"}
    )

    assert result["final_reply"] == "公开资料建议多休息。"
    assert result["rag_sources"] == []
    assert len(result["messages"]) == 1
    second_turn = scripted.seen_messages[1]
    assert any("网页片段：多休息" in str(message.content) for message in second_turn)


def test_fast_node_ignores_hospital_knowledge_tool_calls(monkeypatch):
    scripted = _ScriptedModel(
        [
            [_tool_call("search_hospital_knowledge", {"query": "儿科楼层"}, "call-1")],
            [_text("请关闭快速模式再问院内规定。")],
        ]
    )
    monkeypatch.setattr(fast_mod, "model", scripted)

    result = fast_mod.fast_node(
        {"messages": [HumanMessage(content="儿科在几楼")], "conversation_id": "c1"}
    )

    assert result["rag_sources"] == []
    second_turn = scripted.seen_messages[1]
    assert any("没有名为 search_hospital_knowledge" in str(message.content) for message in second_turn)


class _StubTool:
    """替身工具。web_search 是 pydantic 模型，直接给实例打补丁不可靠，换整个对象。"""

    def __init__(self, name, result):
        self.name = name
        self.result = result

    def invoke(self, args):
        return self.result


def test_fast_node_forces_an_answer_when_tool_budget_runs_out(monkeypatch):
    call_turn = [_tool_call("web_search", {"query": "感冒"}, "call-x")]
    scripted = _ScriptedModel(
        [call_turn] * fast_mod.MAX_TOOL_ITERATIONS + [[_text("这是兜底答案。")]]
    )
    monkeypatch.setattr(fast_mod, "model", scripted)
    monkeypatch.setattr(fast_mod, "web_search", _StubTool("web_search", "网页片段"))

    result = fast_mod.fast_node(
        {"messages": [HumanMessage(content="感冒")], "conversation_id": "c1"}
    )

    assert result["final_reply"] == "这是兜底答案。"


def test_fast_node_falls_back_when_model_returns_nothing(monkeypatch):
    scripted = _ScriptedModel([[_text("   ")]])
    monkeypatch.setattr(fast_mod, "model", scripted)

    result = fast_mod.fast_node(
        {"messages": [HumanMessage(content="你好")], "conversation_id": "c1"}
    )

    assert result["final_reply"] == "抱歉，我这次没能给出有效回答，请换个说法再问一次。"


def test_fast_graph_has_no_routing_or_summarizing_hop():
    from app.graphs.hospital import graphs

    nodes = set(graphs.build_fast_graph().get_graph().nodes)

    assert "fast_node" in nodes
    assert "summarize_node" in nodes
    # 快速模式的全部意义就是不走这三个节点。
    assert "begin_node" not in nodes
    assert "final_node" not in nodes
    assert "knowledge_node" not in nodes


def test_fast_system_prompt_includes_beijing_clock():
    prompt = fast_mod.build_fast_system_prompt(FROZEN_NOW)

    assert "当前时间：2026-09-01 星期二 11:15（北京时间）。" in prompt
    assert prompt.startswith(fast_mod.FAST_SYSTEM_PROMPT)


def test_fast_prompt_answers_weekday_from_clock():
    assert "星期几" in fast_mod.FAST_SYSTEM_PROMPT


def test_fast_node_uses_request_clock(monkeypatch):
    scripted = _ScriptedModel([[_text("今天是星期二。")]])
    monkeypatch.setattr(fast_mod, "model", scripted)

    result = fast_mod.fast_node(
        {"messages": [HumanMessage(content="今天星期几")], "conversation_id": "c1"},
        _graph_runtime(CONTEXT),
    )

    assert result["final_reply"] == "今天是星期二。"
    system = scripted.seen_messages[0][0]
    assert "当前时间：2026-09-01 星期二 11:15（北京时间）。" in system.content
