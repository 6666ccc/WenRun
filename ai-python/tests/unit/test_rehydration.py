from langchain_core.messages import AIMessage, HumanMessage

from app.graphs.hospital.rehydration import build_rehydrated_messages
from app.models.chat import RecoveryMessage


def test_rehydration_preserves_role_order_and_appends_current_turn():
    messages = build_rehydrated_messages(
        [
            RecoveryMessage(id=1, role="user", content="上一问"),
            RecoveryMessage(id=2, role="assistant", content="上一答"),
        ],
        "当前问题",
    )

    assert [message.content for message in messages] == ["上一问", "上一答", "当前问题"]
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)


def test_rehydration_deduplicates_ids_and_respects_token_budget():
    messages = build_rehydrated_messages(
        [
            RecoveryMessage(id=1, role="user", content="旧消息"),
            RecoveryMessage(id=1, role="user", content="重复消息"),
            RecoveryMessage(id=2, role="assistant", content="较新的回答"),
        ],
        "当前问题",
        max_tokens=15,
    )

    contents = [message.content for message in messages]
    assert contents[-1] == "当前问题"
    assert "重复消息" not in contents
    assert len(contents) < 4
