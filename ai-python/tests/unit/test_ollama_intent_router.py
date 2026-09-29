from types import SimpleNamespace

from app.intent import cascade
from app.intent.ollama_classifier import OllamaIntentClassifier
from app.intent.prediction import IntentPrediction


class _StructuredResponse:
    def __init__(self, parsed):
        self.parsed = parsed

    def invoke(self, messages):
        return {
            "parsed": self.parsed,
            "raw": SimpleNamespace(content=""),
            "parsing_error": None,
        }


def _classifier(parsed):
    classifier = OllamaIntentClassifier.__new__(OllamaIntentClassifier)
    classifier.version = "ollama:test-model"
    classifier.structured_model = _StructuredResponse(parsed)
    classifier.acceptance_threshold = 0.7
    classifier.ambiguity_margin = 0.15
    return classifier


def _decision(
    *,
    knowledge=0.0,
    chat=0.0,
    tools=0.0,
    selected=None,
    out_of_scope=False,
    uncertain=False,
):
    return {
        "selected_agents": selected if selected is not None else [],
        "scores": {"knowledge": knowledge, "chat": chat, "tools": tools},
        "out_of_scope": out_of_scope,
        "uncertain": uncertain,
    }


def test_structured_ollama_result_routes_confident_label():
    prediction = _classifier(_decision(tools=0.9, selected=["tools"])).predict(
        "我想找一位医生"
    )

    assert prediction.accepted is True
    assert prediction.selected_agents == ["tools"]
    assert prediction.scores["tools"] == 0.9


def test_structured_ollama_result_rejects_inconsistent_scores():
    prediction = _classifier(_decision(tools=0.9, selected=["knowledge"])).predict(
        "我想找一位医生"
    )

    assert prediction.accepted is False
    assert prediction.reason == "invalid_output"
    assert prediction.selected_agents == []


def test_structured_ollama_result_escalates_low_score():
    prediction = _classifier(_decision(tools=0.6, selected=["tools"])).predict(
        "我想找一位医生"
    )

    assert prediction.accepted is False
    assert prediction.reason == "low_confidence"


def test_ollama_backend_keeps_local_route(monkeypatch):
    monkeypatch.setattr(
        cascade,
        "get_settings",
        lambda: SimpleNamespace(
            intent_backend="ollama", intent_ollama_model="local-model"
        ),
    )
    monkeypatch.setattr(
        cascade,
        "get_ollama_intent_classifier",
        lambda: SimpleNamespace(
            predict=lambda text: IntentPrediction(["tools"], {"tools": 0.9}, True, 0.8)
        ),
    )
    monkeypatch.setattr(
        cascade,
        "get_jev_intent_classifier",
        lambda: (_ for _ in ()).throw(AssertionError("Jev must not be called")),
    )

    result = cascade.route_locally("我想找一位医生")

    assert result.accepted
    assert result.stage == "ollama_model"
    assert result.selected_agents == ["tools"]
    assert result.model_version == "ollama:local-model"
