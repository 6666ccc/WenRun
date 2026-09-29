import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.intent import cascade, jev_classifier
from app.intent.jev_classifier import JevIntentClassifier
from app.intent.prediction import IntentPrediction


def _response(**overrides):
    probabilities = {
        "knowledge": 0.05,
        "chat": 0.05,
        "tools": 0.95,
        "out_of_scope": 0.01,
        "uncertain": 0.01,
    }
    probabilities.update(overrides)
    return {
        "answers": {
            key: {"type": "noul", "noul": value} for key, value in probabilities.items()
        }
    }


@pytest.fixture
def configure(monkeypatch):
    def setup(payload=None, *, key="test-key", status=200, error=None):
        settings = Settings(
            _env_file=None, intent_backend="jev", tokendance_api_key=key
        )
        monkeypatch.setattr(jev_classifier, "get_settings", lambda: settings)
        monkeypatch.setattr(cascade, "get_settings", lambda: settings)
        requests = []

        def handle(request):
            requests.append(request)
            if error:
                raise error
            return httpx.Response(status, json=payload)

        client_type = httpx.Client
        monkeypatch.setattr(
            jev_classifier.httpx,
            "Client",
            lambda **kwargs: client_type(
                transport=httpx.MockTransport(handle), **kwargs
            ),
        )
        classifier = JevIntentClassifier()
        monkeypatch.setattr(cascade, "get_jev_intent_classifier", lambda: classifier)
        return classifier, requests

    return setup


def test_decisions_protocol_and_multilabel_result(configure):
    classifier, requests = configure(_response(knowledge=0.92, chat=0.88))
    prediction = classifier.predict("  医疗、情绪和业务混合需求  ")
    assert prediction.accepted
    assert prediction.selected_agents == ["knowledge", "chat", "tools"]
    (request,) = requests
    assert str(request.url) == "https://tokendance.space/gateway/typesafe/v1/systemone"
    assert request.headers["Authorization"] == "Bearer test-key"
    payload = json.loads(request.content)
    assert payload["model"] == "bocha-jev-v1"
    assert payload["state"] == {"patient_message": "医疗、情绪和业务混合需求"}
    assert set(payload["questions"]) == {
        "knowledge",
        "chat",
        "tools",
        "out_of_scope",
        "uncertain",
    }
    assert all(question["type"] == "noul" for question in payload["questions"].values())
    assert request.extensions["timeout"]["read"] == 10.0
    assert "messages" not in payload


@pytest.mark.parametrize("key", ["", " \t"])
def test_blank_key_skips_jev_and_falls_back_to_ollama(configure, monkeypatch, key):
    _, requests = configure(key=key)
    ollama_inputs = []

    def predict(text):
        ollama_inputs.append(text)
        return IntentPrediction(["tools"], {"tools": 0.9}, True, 0.8)

    monkeypatch.setattr(
        cascade,
        "get_ollama_intent_classifier",
        lambda: SimpleNamespace(predict=predict),
    )
    result = cascade.route_locally("我想找一位医生")
    assert requests == []
    assert ollama_inputs == ["我想找一位医生"]
    assert result.accepted
    assert result.stage == "ollama_model"
    assert (
        result.model_version == f"ollama:{cascade.get_settings().intent_ollama_model}"
    )
    assert result.escalation_reason is None
    assert result.selected_agents == ["tools"]


@pytest.mark.parametrize("unavailable", [False, True])
def test_blank_key_escalates_only_after_ollama_fails_or_is_uncertain(
    configure, monkeypatch, unavailable
):
    _, requests = configure(key="")
    ollama_inputs = []

    def predict(text):
        ollama_inputs.append(text)
        if unavailable:
            raise RuntimeError("Ollama unavailable")
        return IntentPrediction(["tools"], {"tools": 0.6}, False, 0.2, "low_confidence")

    monkeypatch.setattr(
        cascade,
        "get_ollama_intent_classifier",
        lambda: SimpleNamespace(predict=predict),
    )
    result = cascade.route_locally("我想找一位医生")
    assert requests == []
    assert ollama_inputs == ["我想找一位医生"]
    assert not result.accepted
    assert result.stage == "llm_required"
    assert result.escalation_reason == (
        "ollama_unavailable" if unavailable else "low_confidence"
    )
    assert (
        result.model_version == f"ollama:{cascade.get_settings().intent_ollama_model}"
    )
    assert result.selected_agents == []


def test_jev_routes_and_emits_backend_metadata(configure):
    configure(_response())
    result = cascade.route_locally("我想找一位医生")
    assert result.accepted
    assert result.stage == "jev_model"
    assert result.selected_agents == ["tools"]
    assert result.metadata()["model_version"] == "jev:bocha-jev-v1"
    assert result.metadata()["router_version"] == "cascade-v3"


@pytest.mark.parametrize(
    "overrides, reason",
    [
        ({"tools": 0.6}, "low_confidence"),
        ({"knowledge": 0.49}, "low_confidence"),
        ({"knowledge": 0.51}, "low_confidence"),
        ({"out_of_scope": 0.4}, "low_confidence"),
        ({"out_of_scope": 0.9}, "local_out_of_scope"),
        ({"uncertain": 0.9}, "local_uncertain"),
        ({"tools": 0.05}, "local_uncertain"),
    ],
)
def test_uncertain_decisions_never_supply_fallback_labels(configure, overrides, reason):
    configure(_response(**overrides))
    result = cascade.route_locally("我想找一位医生")
    assert not result.accepted
    assert result.stage == "llm_required"
    assert result.escalation_reason == reason
    assert result.selected_agents == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"answers": {}},
        {"answers": []},
        _response(tools=1.1),
        _response(tools=-0.1),
        _response(tools="0.9"),
        _response(tools=True),
        _response(tools=None),
        {
            "answers": {
                **_response()["answers"],
                "tools": {"type": "choice", "noul": 0.9},
            }
        },
    ],
)
def test_invalid_decisions_are_rejected(configure, payload):
    classifier, _ = configure(payload)
    result = classifier.predict("test")
    assert not result.accepted
    assert result.reason == "invalid_output"


@pytest.mark.parametrize("status", [401, 402, 429, 500])
def test_http_errors_escalate_without_retry(configure, status):
    _, requests = configure({"error": "unavailable"}, status=status)
    result = cascade.route_locally("我想找一位医生")
    assert result.escalation_reason == "jev_unavailable"
    assert not result.accepted
    assert len(requests) == 1


def test_timeout_escalates(configure):
    _, requests = configure(error=httpx.ReadTimeout("timeout"))
    result = cascade.route_locally("我想找一位医生")
    assert result.escalation_reason == "jev_unavailable"
    assert len(requests) == 1


def test_rules_and_conditionals_do_not_call_jev(configure):
    _, requests = configure()
    assert cascade.route_locally("谢谢").stage == "rules"
    urgent = cascade.route_locally("突然胸痛而且喘不上气，帮我挂号")
    assert "knowledge" in urgent.selected_agents
    conditional = cascade.route_locally("如果能约就帮我挂号")
    assert conditional.escalation_reason == "conditional_request_requires_reasoning"
    assert requests == []


def test_settings_only_allow_jev_and_ollama(monkeypatch):
    monkeypatch.delenv("INTENT_BACKEND", raising=False)
    assert Settings(_env_file=None).intent_backend == "jev"
    assert Settings(_env_file=None, intent_backend="ollama").intent_backend == "ollama"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, intent_backend="sklearn")
