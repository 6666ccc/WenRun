import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

import pytest

from app.api.routes import chat as chat_route
from app.graphs.hospital.confirmation import decision_from_text


@pytest.mark.parametrize(
    "text",
    ["确认", "好的", "好的，确认", "嗯，可以", "是的", "就这个", "OK", "没问题，谢谢"],
)
def test_decision_from_text_accepts_short_affirmations(text):
    assert decision_from_text(text) == "approve"


@pytest.mark.parametrize(
    "text",
    ["不用了", "算了，不用了", "取消", "先不挂了", "不要", "再想想吧", "no"],
)
def test_decision_from_text_accepts_short_refusals(text):
    assert decision_from_text(text) == "reject"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "确认一下李医生是男的还是女的",
        "好的，不用了",
        "可以改成上午吗",
        "确认，另外帮我看看儿科",
        "张伟医生是什么职称？",
        "好的好的好的好的好的好的好",
    ],
)
def test_decision_from_text_leaves_ambiguous_or_longer_messages_to_chat(text):
    assert decision_from_text(text) is None


def test_resume_command_maps_a_single_interrupt_without_client_id():
    command, code, message = chat_route._resume_command(
        "approve",
        None,
        [{"id": "int-1", "kind": "registration_create"}],
    )

    assert command is not None
    assert command.resume == {"int-1": "approve"}
    assert code is None
    assert message is None


def test_resume_command_rejects_other_pending_interrupts():
    command, code, message = chat_route._resume_command(
        "approve",
        "int-1",
        [
            {"id": "int-1", "kind": "registration_create"},
            {"id": "int-2", "kind": "registration_cancel"},
        ],
    )

    assert command is not None
    assert command.resume == {"int-1": "approve", "int-2": "reject"}
    assert code is None
    assert message is None


def test_resume_command_conflicts_when_multiple_pending_lack_an_id():
    command, code, message = chat_route._resume_command(
        "approve",
        None,
        [
            {"id": "int-1", "kind": "registration_create"},
            {"id": "int-2", "kind": "registration_cancel"},
        ],
    )

    assert command is None
    assert code == "AI_RESUME_CONFLICT"
    assert message == "请重新发起挂号"


def test_resume_command_is_stale_when_nothing_is_pending():
    command, code, message = chat_route._resume_command("approve", "int-1", [])

    assert command is None
    assert code == "AI_RESUME_STALE"
    assert message == "没有待确认事项，请重新发起办理"


def test_resume_command_is_stale_when_interrupt_id_does_not_match():
    command, code, message = chat_route._resume_command(
        "approve",
        "int-9",
        [{"id": "int-1", "kind": "registration_create"}],
    )

    assert command is None
    assert code == "AI_RESUME_STALE"
    assert message == "请重新发起挂号"
