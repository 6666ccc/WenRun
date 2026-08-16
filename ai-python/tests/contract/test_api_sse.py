from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_is_available_without_api_key():
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_requires_internal_api_key():
    response = client.post(
        "/v1/chat",
        json={"message": "你好", "conversationId": "c-1"},
    )
    assert response.status_code == 401


def test_sse_encoder_uses_data_frame():
    from app.models.sse import ChatStreamEvent
    from app.services.sse import encode_sse

    frame = encode_sse(ChatStreamEvent(type="status", content="routing"))
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
