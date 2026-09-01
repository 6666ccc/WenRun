from datetime import date

import httpx
import pytest

from app.core.config import Settings
from app.services.java_tool_client import JavaToolClient, JavaToolClientError


def _client(handler) -> JavaToolClient:
    return JavaToolClient(
        Settings(java_tool_base_url="http://java.internal", java_tool_timeout_seconds=2),
        transport=httpx.MockTransport(handler),
    )


def _envelope(data) -> dict:
    return {"code": 200, "message": "success", "data": data}


def test_list_departments_forwards_delegation_and_trace_headers():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/internal/ai-tools/departments"
        assert request.url.params["status"] == "1"
        assert request.headers["Authorization"] == "Bearer delegated-token"
        assert request.headers["X-Request-Id"] == "trace-123"
        return httpx.Response(200, json=_envelope([{"id": 1, "deptCode": "IM", "deptName": "内科"}]))

    departments = _client(handler).list_departments("delegated-token", "trace-123")

    assert departments[0].id == 1
    assert departments[0].name == "内科"
    assert departments[0].code == "IM"


def test_java_tool_client_rejects_blank_base_url():
    with pytest.raises(JavaToolClientError, match="not configured"):
        JavaToolClient(Settings(java_tool_base_url=""))


def test_list_departments_rejects_non_success_response():
    client = _client(lambda request: httpx.Response(401, json={"code": 401, "message": "unauthorized"}))

    with pytest.raises(JavaToolClientError, match="HTTP 401"):
        client.list_departments("delegated-token", "trace-123")


def test_business_failure_inside_http_200_envelope_is_an_error():
    client = _client(
        lambda request: httpx.Response(200, json={"code": 403, "message": "当前账号还没有绑定患者档案"})
    )

    with pytest.raises(JavaToolClientError, match="当前账号还没有绑定患者档案"):
        client.list_my_registrations("delegated-token", "trace-123")


def test_list_staff_filters_by_department():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/internal/ai-tools/staff"
        assert request.url.params["deptId"] == "1"
        assert request.url.params["status"] == "1"
        return httpx.Response(
            200,
            json=_envelope([{"id": 8, "name": "张医生", "title": "主任医师", "deptName": "内科"}]),
        )

    doctors = _client(handler).list_staff("delegated-token", "trace-123", dept_id=1)

    assert doctors[0].name == "张医生"
    assert doctors[0].title == "主任医师"
    assert doctors[0].dept_name == "内科"


def test_list_schedules_serializes_work_date_as_iso():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/internal/ai-tools/schedules"
        assert request.url.params["deptId"] == "1"
        assert request.url.params["workDate"] == "2026-09-02"
        return httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "id": 9,
                        "deptName": "内科",
                        "staffName": "张医生",
                        "workDate": "2026-09-02",
                        "timePeriod": "上午",
                        "totalCount": 20,
                        "remainingCount": 5,
                        "registerFee": 10.0,
                    }
                ]
            ),
        )

    schedules = _client(handler).list_schedules(
        "delegated-token",
        "trace-123",
        dept_id=1,
        work_date=date(2026, 9, 2),
    )

    assert schedules[0].remaining_count == 5
    assert schedules[0].register_fee == "10.0"


def test_list_my_registrations_never_sends_a_patient_id():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/internal/ai-tools/registrations"
        assert "patientId" not in request.url.params
        return httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "id": 5,
                        "regNo": "R-2026-0001",
                        "deptName": "内科",
                        "staffName": "张医生",
                        "workDate": "2026-09-02",
                        "timePeriod": "上午",
                        "status": 1,
                    }
                ]
            ),
        )

    registrations = _client(handler).list_my_registrations("delegated-token", "trace-123")

    assert registrations[0].reg_no == "R-2026-0001"
    assert registrations[0].status == 1
