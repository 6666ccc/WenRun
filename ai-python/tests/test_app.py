from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from app.api.routes import chat as chat_route
from app.core.config import get_settings
from app.main import create_app


def test_health_endpoint_reports_service_liveness():
    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_endpoint_runs_graph(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()
    captured: dict = {}

    class FakeGraph:
        def invoke(self, state):
            captured["state"] = state
            return {
                "final_reply": "已生成回复",
                "selected_agents": ["knowledge"],
                "rag_sources": [{"id": "S1", "title": "院内资料", "page": 1}],
            }

    monkeypatch.setattr(chat_route, "graph", FakeGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat",
        headers={"X-Api-Key": "test-key"},
        json={
            "message": "感冒怎么办",
            "conversationId": "demo",
            "userContext": {"patientId": 12},
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "已生成回复",
        "status": "completed",
        "conversationId": "demo",
        "selectedAgents": ["knowledge"],
        "sources": [{"id": "S1", "title": "院内资料", "page": 1}],
    }
    assert captured["state"]["conversation_id"] == "demo"
    assert captured["state"]["patient_id"] == 12
    assert isinstance(captured["state"]["messages"][0], HumanMessage)
    assert captured["state"]["messages"][0].content == "感冒怎么办"
