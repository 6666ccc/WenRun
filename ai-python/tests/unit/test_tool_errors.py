from app.services.java_tools.client import JavaToolsClient, ToolFailure


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self.text = text

    def json(self):
        return self._payload


class FakeHttp:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        self.calls.append({"method": method, "url": url, "headers": headers, "json": json})
        if self.error:
            raise self.error
        return self.response


def test_timeout_maps_to_java_tool_timeout():
    import httpx

    client = JavaToolsClient("http://java", http=FakeHttp(error=httpx.TimeoutException("t")))
    try:
        client.request("GET", "/api/internal/ai-tools/schedules", "read-token")
        raise AssertionError("expected ToolFailure")
    except ToolFailure as failure:
        assert failure.code == "JAVA_TOOL_TIMEOUT"
        assert failure.retryable is True


def test_stable_java_error_code_is_preserved():
    client = JavaToolsClient(
        "http://java",
        http=FakeHttp(FakeResponse(409, {"code": "SLOT_SOLD_OUT", "message": "号源已满"})),
    )
    try:
        client.request("POST", "/api/internal/ai-tools/registrations", "write-token", json={})
        raise AssertionError("expected ToolFailure")
    except ToolFailure as failure:
        assert failure.code == "SLOT_SOLD_OUT"
        assert "号源" in failure.safe_message
        assert failure.retryable is False


def test_authorization_header_is_not_logged(caplog):
    import logging

    from app.core.logging import sanitize

    caplog.set_level(logging.INFO)
    client = JavaToolsClient(
        "http://java",
        http=FakeHttp(FakeResponse(200, [])),
    )
    client.request("GET", "/api/internal/ai-tools/depts", "super-secret-token")
    assert "super-secret-token" not in caplog.text
    assert "Authorization" not in caplog.text
    assert "super-secret-token" not in sanitize("Authorization: Bearer super-secret-token")


def test_query_tool_retries_5xx_but_create_does_not():
    class FlakyHttp:
        def __init__(self):
            self.calls = 0

        def request(self, method, url, headers=None, json=None, timeout=None):
            self.calls += 1
            if self.calls < 3:
                return FakeResponse(503, {"code": "JAVA_TOOL_UNAVAILABLE"})
            return FakeResponse(200, [])

    http = FlakyHttp()
    client = JavaToolsClient("http://java", http=http)
    assert client.request("GET", "/api/internal/ai-tools/depts", "read-token") == []
    assert http.calls == 3

    write_http = FakeHttp(FakeResponse(503, {"code": "JAVA_TOOL_UNAVAILABLE"}))
    write_client = JavaToolsClient("http://java", http=write_http)
    try:
        write_client.request("POST", "/api/internal/ai-tools/registrations", "write-token", json={})
        raise AssertionError("expected ToolFailure")
    except ToolFailure as failure:
        assert failure.code == "JAVA_TOOL_UNAVAILABLE"
    assert len(write_http.calls) == 1
