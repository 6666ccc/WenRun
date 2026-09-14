import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.intent.metrics import reset_route_metrics
from app.main import create_app


def test_intent_metrics_endpoint_requires_internal_api_key(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "metrics-test-key")
    get_settings.cache_clear()
    reset_route_metrics()
    client = TestClient(create_app())

    rejected = client.get("/v1/metrics/intent-routing")
    accepted = client.get(
        "/v1/metrics/intent-routing",
        headers={"X-Api-Key": "metrics-test-key"},
    )

    assert rejected.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["scope"] == "current_process"
    assert accepted.json()["total"] == 0
    get_settings.cache_clear()
