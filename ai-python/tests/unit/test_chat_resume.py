import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from app.api.routes import chat as chat_route


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
