import pytest

from app.graphs.hospital import rehydration as mod
from app.graphs.hospital.tools.context import HospitalToolContext
from app.models.chat import ChatRequest
from app.services.java_tool_client import JavaToolClientError


def test_all_uncovered_messages_across_pages_are_recovered(monkeypatch):
    calls = []

    class Client:
        def recovery_page(self, *args, after_id, upper_id, **kwargs):
            calls.append((after_id, upper_id))
            end = min(after_id + 200, upper_id)
            return {
                "messages": [
                    {
                        "id": i,
                        "role": "user",
                        "content": "未解决事项" * 20,
                        "clientRequestId": f"request{i}",
                    }
                    for i in range(after_id + 1, end + 1)
                ],
                "hasMore": end < upper_id,
            }

    monkeypatch.setattr(mod, "JavaToolClient", Client)
    request = ChatRequest(
        message="继续",
        conversationId="c",
        recoveryUpperId=450,
        recoverySummary={"last_message_id": 10},
    )
    recovered = mod.fetch_recovery_messages(request, HospitalToolContext("token"))
    assert len(recovered) == 440
    assert calls == [(10, 450), (210, 450), (410, 450)]
    rebuilt = mod.build_rehydrated_messages(recovered, "继续", max_tokens=100)
    assert len(rebuilt) == 441


def test_premature_end_of_recovery_fails_closed(monkeypatch):
    class Client:
        def recovery_page(self, *args, **kwargs):
            return {"messages": [], "hasMore": False}

    monkeypatch.setattr(mod, "JavaToolClient", Client)
    request = ChatRequest(message="继续", conversationId="c", recoveryUpperId=100)
    with pytest.raises(JavaToolClientError, match="未完成"):
        mod.fetch_recovery_messages(request, HospitalToolContext("token"))
