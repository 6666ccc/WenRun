from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.graphs.hospital.nodes import begin
from app.intent import LocalRouteResult


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


def _force_llm(monkeypatch):
    monkeypatch.setattr(
        begin,
        "_route_locally",
        lambda text: LocalRouteResult(
            accepted=False,
            escalation_reason="test_forces_llm",
        ),
    )


def test_begin_prompt_limits_knowledge_to_medical_topics():
    assert "只处理医疗知识" in begin.BEGIN_SYSTEM_PROMPT
    assert "“儿科在几楼” → chat" in begin.BEGIN_SYSTEM_PROMPT
    assert "“儿科在几楼” → knowledge" not in begin.BEGIN_SYSTEM_PROMPT
    assert "out_of_scope" in begin.BEGIN_SYSTEM_PROMPT


def test_begin_prompt_routes_registration_actions_to_tools():
    assert "“帮我挂号” → tools" in begin.BEGIN_SYSTEM_PROMPT
    assert "退号" in begin.BEGIN_SYSTEM_PROMPT
    assert "办理请求" in begin.BEGIN_SYSTEM_PROMPT


def test_begin_prompt_routes_current_time_to_chat():
    assert "“几点了” → chat" in begin.BEGIN_SYSTEM_PROMPT
    assert "“你是谁” → chat" in begin.BEGIN_SYSTEM_PROMPT


def test_begin_node_uses_model_json_without_tool_strategy(monkeypatch):
    _force_llm(monkeypatch)
    stub_model = StubModel(
        [AIMessage(content='{"selected_agents":["knowledge","tools"]}')]
    )
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="我感冒了，帮我挂明天内科")]})

    assert result["selected_agents"] == ["knowledge", "tools"]
    assert len(stub_model.calls) == 1
    assert isinstance(stub_model.calls[0][0], SystemMessage)
    assert "只返回一个 JSON 对象" in stub_model.calls[0][0].content


def test_begin_node_asks_model_to_repair_invalid_json_once(monkeypatch):
    _force_llm(monkeypatch)
    stub_model = StubModel(
        [
            AIMessage(content="我建议走 knowledge"),
            AIMessage(content='{"selected_agents":["knowledge"]}'),
        ]
    )
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="普通感冒有什么症状")]})

    assert result["selected_agents"] == ["knowledge"]
    assert len(stub_model.calls) == 2
    assert isinstance(stub_model.calls[1][0], SystemMessage)
    assert "上一次无效输出如下" in stub_model.calls[1][0].content


def test_begin_node_uses_local_hint_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr(
        begin,
        "_route_locally",
        lambda text: LocalRouteResult(
            accepted=False,
            selected_agents=["knowledge"],
            escalation_reason="low_confidence",
            scores={"knowledge": 0.51, "chat": 0.30, "tools": 0.44},
        ),
    )
    stub_model = StubModel([RuntimeError("quota exhausted"), RuntimeError("quota exhausted")])
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="联网搜索一下感冒的症状")]})

    assert result["selected_agents"] == ["knowledge"]
    assert result["router_fallback"] is False
    assert result["router_response"] is None
    assert result["intent_route"]["fallback_reason"] == "llm_unavailable_use_local"


def test_begin_node_routes_identity_without_llm(monkeypatch):
    stub_model = StubModel([])
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="你是谁？")]})

    assert result["selected_agents"] == ["chat"]
    assert result["router_fallback"] is False
    assert result["intent_route"]["matched_rules"] == ["exact_identity"]
    assert len(stub_model.calls) == 0


def test_begin_node_falls_back_to_chat_after_invalid_repair(monkeypatch):
    _force_llm(monkeypatch)
    stub_model = StubModel(
        [AIMessage(content='{"selected_agents":["other"]}'), AIMessage(content="[]")]
    )
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="随便说点什么")]})

    assert result["selected_agents"] == ["chat"]
    assert result["router_fallback"] is True
    assert result["intent_route"]["stage"] == "fallback"
    assert len(stub_model.calls) == 2


def test_begin_node_retries_once_when_model_call_fails(monkeypatch):
    _force_llm(monkeypatch)
    stub_model = StubModel(
        [RuntimeError("temporary error"), AIMessage(content='{"selected_agents":["chat"]}')]
    )
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="你好")]})

    assert result["selected_agents"] == ["chat"]
    assert len(stub_model.calls) == 2


def test_begin_node_handles_explicit_out_of_scope_without_freeform_chat(monkeypatch):
    _force_llm(monkeypatch)
    stub_model = StubModel(
        [AIMessage(content='{"selected_agents":[],"out_of_scope":true}')]
    )
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="帮我写一个排序算法")]})

    assert result["selected_agents"] == ["chat"]
    assert result["router_fallback"] is False
    assert result["intent_route"]["out_of_scope"] is True
    assert "超出了当前健康助手" in result["router_response"]
    assert len(stub_model.calls) == 1


def test_begin_node_routes_department_catalog_before_calling_model(monkeypatch):
    stub_model = StubModel([])
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="你们医院有哪些科室？")]})

    assert result["selected_agents"] == ["tools"]
    assert result["intent_route"]["stage"] == "rules"
    assert len(stub_model.calls) == 0


def test_begin_node_keeps_knowledge_when_department_query_has_medical_context(monkeypatch):
    stub_model = StubModel([])
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="感冒了该看哪科")]})

    assert result["selected_agents"] == ["knowledge", "tools"]
    assert len(stub_model.calls) == 0


def test_begin_node_does_not_force_tools_for_department_floor_question(monkeypatch):
    stub_model = StubModel([])
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="儿科在几楼")]})

    assert result["selected_agents"] == ["chat"]
    assert result["intent_route"]["matched_rules"] == ["hospital_static_information"]
    assert len(stub_model.calls) == 0


def test_begin_node_routes_current_time_question_without_llm_fallback(monkeypatch):
    stub_model = StubModel([])
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="几点了")]})

    assert result["selected_agents"] == ["chat"]
    assert result["router_fallback"] is False
    assert result["router_response"] is None
    assert result["intent_route"]["stage"] == "rules"
    assert result["intent_route"]["matched_rules"] == ["exact_clock_question"]
    assert len(stub_model.calls) == 0


def test_begin_node_uses_tools_without_llm_for_department_catalog(monkeypatch):
    stub_model = StubModel([])
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="你们医院有哪些科室？")]})

    assert result["selected_agents"] == ["tools"]
    assert len(stub_model.calls) == 0


def test_begin_node_resets_previous_turn_outputs(monkeypatch):
    stub_model = StubModel([AIMessage(content='{"selected_agents":["chat"]}')])
    monkeypatch.setattr(begin, "model", stub_model)
    result = begin.begin_node({
        "messages": [HumanMessage(content="谢谢你啊")],
        "knowledge_reply": "上一轮的用药建议",
        "rag_sources": [{"id": "S1"}],
        "tools_reply": "上一轮的号源结果",
        "final_reply": "上一轮的最终回复",
    })
    assert result["selected_agents"] == ["chat"]
    for field in (
        "task_plan", "knowledge_reply", "rag_sources", "chat_reply", "tools_reply", "final_reply"
    ):
        assert result[field] is None


def _lightweight_chat(monkeypatch):
    monkeypatch.setattr(
        begin,
        "_route_locally",
        lambda text: LocalRouteResult(
            accepted=True,
            selected_agents=["chat"],
            stage="lightweight_model",
            scores={"chat": 0.9},
        ),
    )


def _followup_state(text="明天下午"):
    return {
        "messages": [
            HumanMessage(content="帮我挂李雷医生的号"),
            AIMessage(content="请问您想约哪一天、上午还是下午？"),
            HumanMessage(content=text),
        ],
        "selected_agents": ["tools"],
        "tools_reply": "请问您想约哪一天、上午还是下午？",
    }


def test_begin_node_escalates_slot_followup_to_llm_instead_of_lightweight_chat(monkeypatch):
    """上一轮业务助手在追问参数时，“明天下午”不能被无上下文的轻量模型判成闲聊。"""

    _lightweight_chat(monkeypatch)
    stub_model = StubModel([AIMessage(content='{"selected_agents":["tools"]}')])
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node(_followup_state())

    assert result["selected_agents"] == ["tools"]
    assert result["intent_route"]["stage"] == "llm"
    assert result["intent_route"]["escalation_reason"] == "pending_followup"
    assert len(stub_model.calls) == 1
    # 带历史的路由上下文里必须能看到上一条追问。
    assert any(
        "请问您想约哪一天" in getattr(message, "content", "") for message in stub_model.calls[0]
    )


def test_begin_node_keeps_lightweight_result_when_previous_turn_was_not_a_question(monkeypatch):
    _lightweight_chat(monkeypatch)
    stub_model = StubModel([])
    monkeypatch.setattr(begin, "model", stub_model)

    state = _followup_state("谢谢")
    state["tools_reply"] = "已为您列出明天的号源。"
    result = begin.begin_node(state)

    assert result["selected_agents"] == ["chat"]
    assert result["intent_route"]["stage"] == "lightweight_model"
    assert len(stub_model.calls) == 0


def test_begin_node_trusts_rules_even_during_followup(monkeypatch):
    stub_model = StubModel([])
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node(_followup_state("你是谁？"))

    assert result["selected_agents"] == ["chat"]
    assert result["intent_route"]["stage"] == "rules"
    assert len(stub_model.calls) == 0


def test_begin_prompt_explains_followup_continuation():
    assert "追问接续" in begin.BEGIN_SYSTEM_PROMPT
    assert "患者：“明天下午” → tools" in begin.BEGIN_SYSTEM_PROMPT
