from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.routes.chat import (
    _confirmations_from_snapshot,
    _discard_unsupported_checkpoint,
)
from app.graphs.hospital.confirmation import resume_command


@pytest.mark.parametrize("kind", ["registration_create", "registration_cancel"])
def test_supported_business_confirmation_still_resumes(kind):
    command, code, _ = resume_command("approve", "i", [{"id": "i", "kind": kind}])
    assert code is None
    assert command.resume == {"i": "approve"}


def test_unsupported_confirmation_is_not_a_resumable_action():
    pending = [{"id": "i", "kind": "obsolete_action"}]
    command, code, _ = resume_command("reject", "i", pending)
    assert command is None
    assert code == "AI_RESUME_STALE"


@pytest.mark.asyncio
async def test_obsolete_checkpoint_is_removed_without_running_its_graph():
    saver = SimpleNamespace(adelete_thread=AsyncMock())
    graph = SimpleNamespace(checkpointer=saver)
    snapshot = SimpleNamespace(interrupts=[SimpleNamespace(id="i", value={"kind": "memory_create"})])
    assert _confirmations_from_snapshot(snapshot) == []
    assert await _discard_unsupported_checkpoint(graph, {"configurable": {"thread_id": "user:1:conversation:c"}}, snapshot)
    saver.adelete_thread.assert_awaited_once_with("user:1:conversation:c")


@pytest.mark.asyncio
async def test_current_registration_checkpoint_is_preserved():
    saver = SimpleNamespace(adelete_thread=AsyncMock())
    snapshot = SimpleNamespace(interrupts=[SimpleNamespace(id="i", value={"kind": "registration_create"})])
    assert not await _discard_unsupported_checkpoint(SimpleNamespace(checkpointer=saver), {}, snapshot)
    saver.adelete_thread.assert_not_called()


@pytest.mark.asyncio
async def test_cache_cleanup_failure_does_not_resume_obsolete_work():
    saver = SimpleNamespace(adelete_thread=AsyncMock(side_effect=OSError("offline")))
    snapshot = SimpleNamespace(interrupts=[SimpleNamespace(value={"kind": "obsolete_action"})])
    with pytest.raises(HTTPException) as caught:
        await _discard_unsupported_checkpoint(SimpleNamespace(checkpointer=saver), {"configurable": {"thread_id": "c"}}, snapshot)
    assert caught.value.status_code == 503
