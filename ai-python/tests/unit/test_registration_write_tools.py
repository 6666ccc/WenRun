import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from datetime import datetime

import pytest
from langchain.tools import ToolRuntime

from app.graphs.hospital.tools import registration_write as write_module
from app.graphs.hospital.tools.context import CLINIC_TZ, HospitalToolContext
from app.services.java_tool_client import (
    JavaToolBusinessError,
    JavaToolClientError,
    Registration,
    Schedule,
)

FROZEN_NOW = datetime(2026, 9, 1, 11, 15, tzinfo=CLINIC_TZ)
CONTEXT = HospitalToolContext(
    "delegated-token",
    "trace-123",
    now=FROZEN_NOW,
    conversation_id="conversation-1",
    writes_enabled=True,
)

SCHEDULE = Schedule(
    id=9,
    dept_name="内科",
    staff_name="张伟",
    work_date="2026-09-04",
    time_period="下午",
    total_count=20,
    remaining_count=3,
    register_fee="50.00",
)

REGISTRATION = Registration(
    id=55,
    reg_no="REG-2026-0001",
    dept_name="内科",
    staff_name="张伟",
    work_date="2026-09-04",
    time_period="下午",
    status=1,
    reg_fee="50.00",
)


def _runtime() -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=CONTEXT,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="call-1",
        store=None,
    )


class FakeClient:
    """记录调用顺序，便于断言「确认前绝不写库」。"""

    def __init__(self, *, schedule=SCHEDULE, registrations=None, create_error=None):
        self.schedule = schedule
        self.registrations = [REGISTRATION] if registrations is None else registrations
        self.create_error = create_error
        self.writes: list[dict] = []

    def get_schedule(self, token, request_id, *, schedule_id):
        return self.schedule

    def list_my_registrations(self, token, request_id):
        return self.registrations

    def create_registration(self, token, request_id, *, schedule_id, idempotency_key):
        if self.create_error is not None:
            raise self.create_error
        self.writes.append({"schedule_id": schedule_id, "idempotency_key": idempotency_key})
        return 55

    def cancel_registration(self, token, request_id, *, registration_id):
        self.writes.append({"registration_id": registration_id})


def _install(monkeypatch, client: FakeClient) -> FakeClient:
    monkeypatch.setattr(write_module, "JavaToolClient", lambda: client)
    return client


def _install_decision(monkeypatch, decision: str) -> None:
    monkeypatch.setattr(write_module, "interrupt", lambda payload: decision)


class Paused(Exception):
    """替身：真实的 interrupt() 会中止本次执行，这里用哨兵异常模拟同样的控制流。"""


def test_create_registration_interrupts_with_authoritative_schedule(monkeypatch):
    client = _install(monkeypatch, FakeClient())
    captured: dict = {}

    def fake_interrupt(payload):
        captured.update(payload)
        raise Paused()

    monkeypatch.setattr(write_module, "interrupt", fake_interrupt)

    with pytest.raises(Paused):
        write_module.create_registration.func(schedule_id=9, runtime=_runtime())

    assert captured["kind"] == "registration_create"
    assert captured["detail"]["staffName"] == "张伟"
    assert captured["detail"]["workDate"] == "2026-09-04"
    assert captured["detail"]["registerFee"] == "50.00"
    # 确认前一次都不能写库。
    assert client.writes == []


def test_create_registration_submits_with_stable_idempotency_key(monkeypatch):
    client = _install(monkeypatch, FakeClient())
    _install_decision(monkeypatch, "approve")

    reply = write_module.create_registration.func(schedule_id=9, runtime=_runtime())

    assert client.writes == [
        {"schedule_id": 9, "idempotency_key": "conversation-1:call-1"}
    ]
    assert "挂号已办好" in reply


def test_create_registration_does_not_write_when_rejected(monkeypatch):
    client = _install(monkeypatch, FakeClient())
    _install_decision(monkeypatch, "reject")

    reply = write_module.create_registration.func(schedule_id=9, runtime=_runtime())

    assert client.writes == []
    assert "没有提交" in reply


def test_create_registration_stops_before_confirming_when_slot_is_full(monkeypatch):
    client = _install(monkeypatch, FakeClient(schedule=Schedule(id=9, remaining_count=0)))

    def fail_interrupt(payload):
        raise AssertionError("号源为 0 时不应该弹确认卡片")

    monkeypatch.setattr(write_module, "interrupt", fail_interrupt)

    assert "已约满" in write_module.create_registration.func(schedule_id=9, runtime=_runtime())
    assert client.writes == []


def test_create_registration_relays_business_rejection_in_chinese(monkeypatch):
    _install(monkeypatch, FakeClient(create_error=JavaToolBusinessError("您已预约该医生此时段，不能重复挂号")))
    _install_decision(monkeypatch, "approve")

    reply = write_module.create_registration.func(schedule_id=9, runtime=_runtime())

    assert "您已预约该医生此时段，不能重复挂号" in reply


def test_create_registration_degrades_when_java_is_unavailable(monkeypatch):
    class BrokenClient(FakeClient):
        def get_schedule(self, token, request_id, *, schedule_id):
            raise JavaToolClientError("Java Tool API is unavailable")

    _install(monkeypatch, BrokenClient())

    assert (
        write_module.create_registration.func(schedule_id=9, runtime=_runtime())
        == "暂时无法查询医院业务信息，请稍后重试。"
    )


def test_cancel_registration_submits_after_approval(monkeypatch):
    client = _install(monkeypatch, FakeClient())
    _install_decision(monkeypatch, "approve")

    reply = write_module.cancel_registration.func(registration_id=55, runtime=_runtime())

    assert client.writes == [{"registration_id": 55}]
    assert "已为您退号" in reply


def test_cancel_registration_rejects_unknown_registration(monkeypatch):
    client = _install(monkeypatch, FakeClient(registrations=[]))

    reply = write_module.cancel_registration.func(registration_id=55, runtime=_runtime())

    assert "没有找到" in reply
    assert client.writes == []


def test_cancel_registration_rejects_already_finished_registration(monkeypatch):
    finished = Registration(id=55, reg_no="REG-1", status=3)
    client = _install(monkeypatch, FakeClient(registrations=[finished]))

    reply = write_module.cancel_registration.func(registration_id=55, runtime=_runtime())

    assert "不是已挂号状态" in reply
    assert client.writes == []


def test_context_defaults_keep_writes_disabled():
    default_context = HospitalToolContext("token", "trace")

    assert default_context.writes_enabled is False
    assert default_context.conversation_id is None
