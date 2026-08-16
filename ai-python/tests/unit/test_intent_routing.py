import pytest
from pydantic import ValidationError


def test_route_maps_only_three_business_intents():
    from app.graphs.hospital.graph import route_by_intent
    assert route_by_intent({"intent": "chat"}) == "chat"
    assert route_by_intent({"intent": "hospital"}) == "hospital"
    assert route_by_intent({"intent": "medical"}) == "medical"


def test_ambiguous_intent_routes_to_clarification():
    from app.graphs.hospital.graph import route_by_intent
    assert route_by_intent({"intent": None}) == "clarify"


def test_unknown_or_missing_intent_routes_to_clarification():
    from app.graphs.hospital.graph import route_by_intent
    assert route_by_intent({"intent": "tool"}) == "clarify"
    assert route_by_intent({"intent": "knowledge"}) == "clarify"
    assert route_by_intent({}) == "clarify"


def test_medical_agent_escalates_danger_signals(fake_medical_agent):
    answer = fake_medical_agent.invoke("胸痛并且呼吸困难")
    assert "急诊" in answer or "急救" in answer
    assert "确诊" not in answer


def test_intent_result_only_allows_three_business_values():
    from app.models.intent_result import IntentResult

    for value in ("chat", "hospital", "medical"):
        assert IntentResult(intent=value).intent == value

    with pytest.raises(ValidationError):
        IntentResult(intent="tool")
    with pytest.raises(ValidationError):
        IntentResult(intent="knowledge")


def test_intent_prompt_routes_mixed_hospital_requests():
    from app.graphs.hospital.prompts.intent import INTENT_SYSTEM_PROMPT

    assert "医院信息 + 办事" in INTENT_SYSTEM_PROMPT
    assert "hospital" in INTENT_SYSTEM_PROMPT


def test_medical_prompt_states_capability_boundary():
    from app.graphs.hospital.prompts.medical import MEDICAL_SYSTEM_PROMPT

    assert "不诊断" in MEDICAL_SYSTEM_PROMPT
    assert "不开药" in MEDICAL_SYSTEM_PROMPT
    assert "不给具体处方剂量" in MEDICAL_SYSTEM_PROMPT
    assert "急诊" in MEDICAL_SYSTEM_PROMPT


class _InfraFailingIntentAgent:
    def invoke(self, payload):
        raise RuntimeError("intent agent timeout")


def test_intent_judgment_propagates_non_classification_errors():
    from app.graphs.hospital.graph import GraphDependencies
    from app.graphs.hospital.nodes.intent_judgment_node import build_intent_judgment_node

    deps = GraphDependencies(
        intent_agent=_InfraFailingIntentAgent(),
        chat_agent=None,
        hospital_agent=None,
        medical_agent=None,
    )
    node = build_intent_judgment_node(deps)
    with pytest.raises(RuntimeError, match="intent agent timeout"):
        node({"messages": [{"role": "user", "content": "你好"}]})


def test_build_graph_is_the_only_compiled_entry():
    import app.graphs.hospital.graph as graph_mod

    assert hasattr(graph_mod, "build_graph")
    assert hasattr(graph_mod, "GraphDependencies")
    assert not hasattr(graph_mod, "run_graph")
    compiled = getattr(graph_mod, "app", None)
    assert compiled is None
