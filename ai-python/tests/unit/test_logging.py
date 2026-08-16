from app.core.logging import sanitize


def test_sanitize_redacts_service_headers_and_bearer_tokens():
    text = (
        "X-Api-Key: super-secret "
        "X-Delegated-Token: delegated-secret "
        "Authorization: Bearer jwt-token-value"
    )
    cleaned = sanitize(text)
    assert "super-secret" not in cleaned
    assert "delegated-secret" not in cleaned
    assert "jwt-token-value" not in cleaned
    assert "X-Api-Key=[redacted]" in cleaned
