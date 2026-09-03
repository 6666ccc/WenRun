"""Python 到 Java 内部 Tool API 的受控客户端。"""

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from app.core.config import Settings, get_settings


class JavaToolClientError(RuntimeError):
    """Java Tool API 不可用、未授权或返回了不符合契约的数据。"""


class JavaToolBusinessError(JavaToolClientError):
    """Java 依据业务规则拒绝了本次请求，message 是可以直接转达给患者的中文文案。"""


@dataclass(frozen=True)
class Department:
    id: int
    name: str
    code: str | None = None


@dataclass(frozen=True)
class Staff:
    id: int
    name: str
    title: str | None = None
    dept_name: str | None = None


@dataclass(frozen=True)
class Schedule:
    id: int
    dept_name: str | None = None
    staff_name: str | None = None
    work_date: str | None = None
    time_period: str | None = None
    total_count: int | None = None
    remaining_count: int | None = None
    register_fee: str | None = None


@dataclass(frozen=True)
class Registration:
    id: int
    reg_no: str | None = None
    dept_name: str | None = None
    staff_name: str | None = None
    work_date: str | None = None
    time_period: str | None = None
    status: int | None = None
    reg_fee: str | None = None


def _required_int(item: dict[str, Any], key: str) -> int:
    value = item.get(key)
    if not isinstance(value, int):
        raise JavaToolClientError(f"Java Tool API returned an invalid {key}")
    return value


def _optional_int(item: dict[str, Any], key: str) -> int | None:
    value = item.get(key)
    return value if isinstance(value, int) else None


def _optional_str(item: dict[str, Any], key: str) -> str | None:
    value = item.get(key)
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None


def _to_schedule(item: dict[str, Any]) -> Schedule:
    return Schedule(
        id=_required_int(item, "id"),
        dept_name=_optional_str(item, "deptName"),
        staff_name=_optional_str(item, "staffName"),
        work_date=_optional_str(item, "workDate"),
        time_period=_optional_str(item, "timePeriod"),
        total_count=_optional_int(item, "totalCount"),
        remaining_count=_optional_int(item, "remainingCount"),
        register_fee=_optional_str(item, "registerFee"),
    )


class JavaToolClient:
    """仅调用受控 Java Tool API；Java 仍是数据与业务规则的唯一所有者。"""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = settings or get_settings()
        if not settings.java_tool_base_url.strip():
            raise JavaToolClientError("JAVA_TOOL_BASE_URL is not configured")
        self._base_url = settings.java_tool_base_url.rstrip("/")
        self._timeout = max(0.1, settings.java_tool_timeout_seconds)
        self._transport = transport

    def list_departments(
        self,
        delegated_token: str,
        request_id: str | None,
        *,
        status: int | None = 1,
    ) -> list[Department]:
        data = self._get_list(
            "/api/internal/ai-tools/departments",
            delegated_token,
            request_id,
            {"status": status},
        )
        departments: list[Department] = []
        for item in data:
            name = _optional_str(item, "deptName")
            if name is None:
                raise JavaToolClientError("Java Tool API returned an incomplete department")
            departments.append(
                Department(
                    id=_required_int(item, "id"),
                    name=name,
                    code=_optional_str(item, "deptCode"),
                )
            )
        return departments

    def list_staff(
        self,
        delegated_token: str,
        request_id: str | None,
        *,
        dept_id: int | None = None,
        status: int | None = 1,
    ) -> list[Staff]:
        data = self._get_list(
            "/api/internal/ai-tools/staff",
            delegated_token,
            request_id,
            {"deptId": dept_id, "status": status},
        )
        staff: list[Staff] = []
        for item in data:
            name = _optional_str(item, "name")
            if name is None:
                raise JavaToolClientError("Java Tool API returned an incomplete staff member")
            staff.append(
                Staff(
                    id=_required_int(item, "id"),
                    name=name,
                    title=_optional_str(item, "title"),
                    dept_name=_optional_str(item, "deptName"),
                )
            )
        return staff

    def list_schedules(
        self,
        delegated_token: str,
        request_id: str | None,
        *,
        dept_id: int | None = None,
        work_date: date | None = None,
        staff_id: int | None = None,
    ) -> list[Schedule]:
        data = self._get_list(
            "/api/internal/ai-tools/schedules",
            delegated_token,
            request_id,
            {
                "deptId": dept_id,
                "workDate": work_date.isoformat() if work_date else None,
                "staffId": staff_id,
            },
        )
        return [_to_schedule(item) for item in data]

    def get_schedule(
        self,
        delegated_token: str,
        request_id: str | None,
        *,
        schedule_id: int,
    ) -> Schedule:
        """按 id 查单条排班。确认卡片必须用这里查回来的权威数据，不能用模型复述的。"""
        data = self._get(
            f"/api/internal/ai-tools/schedules/{schedule_id}",
            delegated_token,
            request_id,
        )
        if not isinstance(data, dict):
            raise JavaToolClientError("Java Tool API returned an invalid schedule")
        return _to_schedule(data)

    def list_my_registrations(
        self,
        delegated_token: str,
        request_id: str | None,
        *,
        status: int | None = None,
    ) -> list[Registration]:
        """患者范围由 Java 依据委托令牌决定，这里不能也不该传 patientId。"""
        data = self._get_list(
            "/api/internal/ai-tools/registrations",
            delegated_token,
            request_id,
            {"status": status},
        )
        return [
            Registration(
                id=_required_int(item, "id"),
                reg_no=_optional_str(item, "regNo"),
                dept_name=_optional_str(item, "deptName"),
                staff_name=_optional_str(item, "staffName"),
                work_date=_optional_str(item, "workDate"),
                time_period=_optional_str(item, "timePeriod"),
                status=_optional_int(item, "status"),
                reg_fee=_optional_str(item, "regFee"),
            )
            for item in data
        ]

    def create_registration(
        self,
        delegated_token: str,
        request_id: str | None,
        *,
        schedule_id: int,
        idempotency_key: str,
    ) -> int:
        """患者维度由 Java 依据委托令牌决定，这里不能也不该传 patientId。"""
        data = self._post(
            "/api/internal/ai-tools/registrations",
            delegated_token,
            request_id,
            {"scheduleId": schedule_id, "idempotencyKey": idempotency_key},
        )
        if not isinstance(data, int):
            raise JavaToolClientError("Java Tool API returned an invalid registration id")
        return data

    def cancel_registration(
        self,
        delegated_token: str,
        request_id: str | None,
        *,
        registration_id: int,
    ) -> None:
        self._post(
            f"/api/internal/ai-tools/registrations/{registration_id}/cancel",
            delegated_token,
            request_id,
            {},
        )

    def _get_list(
        self,
        path: str,
        delegated_token: str,
        request_id: str | None,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        data = self._get(path, delegated_token, request_id, params)
        if not isinstance(data, list):
            raise JavaToolClientError("Java Tool API returned an invalid result envelope")
        for item in data:
            if not isinstance(item, dict):
                raise JavaToolClientError("Java Tool API returned an invalid list item")
        return data

    def _get(
        self,
        path: str,
        delegated_token: str,
        request_id: str | None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        headers = self._headers(delegated_token, request_id)
        query = {key: value for key, value in (params or {}).items() if value is not None}
        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = client.get(path, headers=headers, params=query or None)
        except httpx.HTTPError as exc:
            raise JavaToolClientError("Java Tool API is unavailable") from exc
        return self._unwrap(response)

    def _post(
        self,
        path: str,
        delegated_token: str,
        request_id: str | None,
        payload: dict[str, Any],
    ) -> Any:
        headers = self._headers(delegated_token, request_id)
        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = client.post(path, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise JavaToolClientError("Java Tool API is unavailable") from exc
        return self._unwrap(response)

    def _headers(self, delegated_token: str, request_id: str | None) -> dict[str, str]:
        if not delegated_token.strip():
            raise JavaToolClientError("delegated token is missing")
        headers = {"Authorization": f"Bearer {delegated_token}"}
        if request_id:
            headers["X-Request-Id"] = request_id
        return headers

    def _unwrap(self, response: httpx.Response) -> Any:
        if response.status_code != 200:
            raise JavaToolClientError(f"Java Tool API returned HTTP {response.status_code}")
        try:
            body: dict[str, Any] = response.json()
        except (TypeError, ValueError) as exc:
            raise JavaToolClientError("Java Tool API returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise JavaToolClientError("Java Tool API returned an invalid result envelope")
        # Java 的业务异常同样是 HTTP 200，只在信封里降级 code，必须单独判断。
        # 这里的 message 是给患者看的中文文案，原样保留，不加英文前缀。
        if body.get("code") != 200:
            raise JavaToolBusinessError(
                str(body.get("message") or body.get("code"))
            )
        return body.get("data")
