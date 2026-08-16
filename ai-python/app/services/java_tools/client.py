from uuid import uuid4

import httpx

from app.core.logging import log_event
from app.services.java_tools.models import SAFE_MESSAGES, ToolFailure

__all__ = ["JavaToolsClient", "ToolFailure"]

_RETRYABLE_STATUS = {500, 502, 503, 504}
_QUERY_METHODS = {"GET"}


class JavaToolsClient:
    def __init__(self, base_url: str, http=None, timeout: float = 10.0, max_retries: int = 2):
        self.base_url = base_url.rstrip("/")
        self._http = http
        self.timeout = timeout
        self.max_retries = max_retries

    def request(self, method: str, path: str, token: str, json=None):
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Request-Id": str(uuid4()),
        }
        url = f"{self.base_url}{path}"
        log_event(request_id=headers["X-Request-Id"], tool=path)
        attempts = 1 + self.max_retries if method.upper() in _QUERY_METHODS else 1
        last_error = None
        for attempt in range(attempts):
            try:
                return self._once(method, url, headers, json)
            except ToolFailure as exc:
                last_error = exc
                if not exc.retryable or attempt >= attempts - 1:
                    log_event(
                        request_id=headers["X-Request-Id"],
                        tool=path,
                        error_code=exc.code,
                    )
                    raise
        raise last_error

    def _once(self, method: str, url: str, headers: dict, json):
        try:
            response = self._http_client().request(
                method,
                url,
                headers=headers,
                json=json,
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise ToolFailure("JAVA_TOOL_TIMEOUT", SAFE_MESSAGES["JAVA_TOOL_TIMEOUT"], True) from exc
        except httpx.HTTPError as exc:
            raise ToolFailure("JAVA_TOOL_UNAVAILABLE", SAFE_MESSAGES["JAVA_TOOL_UNAVAILABLE"], True) from exc

        if response.status_code >= 400:
            payload = _safe_json(response)
            code = str(payload.get("code") or "JAVA_TOOL_UNAVAILABLE")
            raise ToolFailure(
                code,
                SAFE_MESSAGES.get(code) or str(payload.get("message") or SAFE_MESSAGES["JAVA_TOOL_UNAVAILABLE"]),
                retryable=response.status_code in _RETRYABLE_STATUS,
            )
        if response.status_code == 204:
            return None
        return _safe_json(response)

    def _http_client(self):
        if self._http is not None:
            return self._http
        return httpx.Client(timeout=self.timeout)


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return {}
