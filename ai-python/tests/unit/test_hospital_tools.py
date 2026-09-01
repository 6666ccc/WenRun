import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from datetime import date, datetime

from langchain.tools import ToolRuntime

from app.graphs.hospital.tools import registrations as registrations_module
from app.graphs.hospital.tools import schedules as schedules_module
from app.graphs.hospital.tools import staff as staff_module
from app.graphs.hospital.tools.context import CLINIC_TZ, HospitalToolContext
from app.services.java_tool_client import Department, Registration, Schedule, Staff

FROZEN_NOW = datetime(2026, 9, 1, 11, 15, tzinfo=CLINIC_TZ)
CONTEXT = HospitalToolContext("delegated-token", "trace-123", now=FROZEN_NOW)


def _tool_runtime() -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=CONTEXT,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="call-1",
        store=None,
    )


class FakeJavaToolClient:
    """记录调用参数的假客户端，让断言集中在 Python 侧的参数换算与措辞上。"""

    calls: dict = {}

    def list_departments(self, delegated_token, request_id):
        assert delegated_token == "delegated-token"
        return [Department(id=1, name="内科"), Department(id=2, name="儿科")]

    def list_staff(self, delegated_token, request_id, *, dept_id=None):
        FakeJavaToolClient.calls["list_staff"] = dept_id
        return [
            Staff(id=8, name="张伟", title="主任医师", dept_name="内科"),
            Staff(id=9, name="李娜", title="主治医师", dept_name="儿科"),
        ]

    def list_schedules(self, delegated_token, request_id, *, dept_id=None, work_date=None, staff_id=None):
        FakeJavaToolClient.calls["list_schedules"] = (dept_id, work_date, staff_id)
        return [
            Schedule(
                id=9,
                dept_name="内科",
                staff_name="张伟",
                work_date="2026-09-02",
                time_period="上午",
                total_count=20,
                remaining_count=5,
                register_fee="10.00",
            )
        ]

    def list_my_registrations(self, delegated_token, request_id):
        return [
            Registration(
                id=5,
                reg_no="R-2026-0001",
                dept_name="内科",
                staff_name="张医生",
                work_date="2026-09-02",
                time_period="上午",
                status=1,
            )
        ]


def test_list_doctors_translates_department_name_to_dept_id(monkeypatch):
    monkeypatch.setattr(staff_module, "JavaToolClient", FakeJavaToolClient)

    reply = staff_module.list_doctors.func(runtime=_tool_runtime(), department="内科")

    assert FakeJavaToolClient.calls["list_staff"] == 1
    assert "张伟" in reply
    assert "主任医师" in reply


def test_list_doctors_reports_unknown_department(monkeypatch):
    monkeypatch.setattr(staff_module, "JavaToolClient", FakeJavaToolClient)

    reply = staff_module.list_doctors.func(runtime=_tool_runtime(), department="骨科")

    assert "没有查到叫「骨科」的科室" in reply


def test_list_schedules_resolves_relative_work_date(monkeypatch):
    monkeypatch.setattr(schedules_module, "JavaToolClient", FakeJavaToolClient)

    reply = schedules_module.list_schedules.func(
        runtime=_tool_runtime(),
        department="内科",
        work_date="明天",
    )

    dept_id, work_date, staff_id = FakeJavaToolClient.calls["list_schedules"]
    assert dept_id == 1
    assert staff_id is None
    assert work_date == date(2026, 9, 2)
    assert "余号 5/20" in reply
    assert "挂号费 10.00" in reply


def test_list_schedules_resolves_doctor_name_to_staff_id(monkeypatch):
    monkeypatch.setattr(schedules_module, "JavaToolClient", FakeJavaToolClient)

    reply = schedules_module.list_schedules.func(
        runtime=_tool_runtime(),
        doctor="张伟医生",
    )

    _, _, staff_id = FakeJavaToolClient.calls["list_schedules"]
    assert staff_id == 8
    assert "张伟" in reply


def test_list_schedules_reports_unknown_doctor(monkeypatch):
    monkeypatch.setattr(schedules_module, "JavaToolClient", FakeJavaToolClient)

    reply = schedules_module.list_schedules.func(runtime=_tool_runtime(), doctor="王芳")

    assert "没有查到叫「王芳」的医生" in reply


def test_list_schedules_rejects_unparsable_work_date(monkeypatch):
    monkeypatch.setattr(schedules_module, "JavaToolClient", FakeJavaToolClient)

    reply = schedules_module.list_schedules.func(runtime=_tool_runtime(), work_date="下下个月某天")

    assert "没看懂就诊日期" in reply


def test_list_my_registrations_renders_status_in_chinese(monkeypatch):
    monkeypatch.setattr(registrations_module, "JavaToolClient", FakeJavaToolClient)

    reply = registrations_module.list_my_registrations.func(runtime=_tool_runtime())

    assert "状态 已挂号" in reply
    assert "R-2026-0001" in reply
