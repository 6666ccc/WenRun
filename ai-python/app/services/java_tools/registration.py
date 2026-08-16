import hashlib


def idempotency_key(conversation_id: str, interrupt_id: str) -> str:
    raw = f"{conversation_id}:{interrupt_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def create_registration(client, token: str, payload: dict):
    return client.request("POST", "/api/internal/ai-tools/registrations", token, json=payload) or {}
