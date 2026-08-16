import json
import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from app.core.config import Settings

_SECRET_KEYS = {
    "delegation_token",
    "authorization",
    "x-delegated-token",
    "x_delegated_token",
    "x-api-key",
    "x_api_key",
    "api_key",
}


def strip_secrets(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if str(key).lower() in _SECRET_KEYS:
                cleaned[key] = "[redacted]"
            else:
                cleaned[key] = strip_secrets(item)
        return cleaned
    if isinstance(value, list):
        return [strip_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(strip_secrets(item) for item in value)
    return value


def protect_checkpointer(saver):
    """Keep the original saver type, but never persist delegation tokens."""
    persisted: list[str] = []
    original_put = saver.put
    original_aput = getattr(saver, "aput", None)
    original_put_writes = getattr(saver, "put_writes", None)
    original_aput_writes = getattr(saver, "aput_writes", None)

    def _record(config, checkpoint, metadata):
        persisted.append(
            json.dumps(
                {"config": config, "checkpoint": checkpoint, "metadata": metadata},
                default=str,
            )
        )

    def put(config, checkpoint, metadata, new_versions):
        config = strip_secrets(config)
        checkpoint = strip_secrets(checkpoint)
        metadata = strip_secrets(metadata)
        _record(config, checkpoint, metadata)
        return original_put(config, checkpoint, metadata, new_versions)

    async def aput(config, checkpoint, metadata, new_versions):
        config = strip_secrets(config)
        checkpoint = strip_secrets(checkpoint)
        metadata = strip_secrets(metadata)
        _record(config, checkpoint, metadata)
        return await original_aput(config, checkpoint, metadata, new_versions)

    saver.put = put
    if original_aput is not None:
        saver.aput = aput
    if original_put_writes is not None:
        saver.put_writes = lambda config, writes, task_id, task_path="": original_put_writes(
            strip_secrets(config), writes, task_id, task_path
        )
    if original_aput_writes is not None:
        async def aput_writes(config, writes, task_id, task_path=""):
            return await original_aput_writes(strip_secrets(config), writes, task_id, task_path)
        saver.aput_writes = aput_writes

    saver.serialized_content = lambda: "\n".join(persisted)
    saver.exists = lambda conversation_id: _exists(saver, conversation_id)
    original_delete = getattr(saver, "delete_thread", None)

    def delete_thread(conversation_id: str) -> None:
        if original_delete is not None:
            original_delete(conversation_id)
            return
        conn = getattr(saver, "conn", None)
        if conn is None:
            return
        for table in ("checkpoints", "checkpoint_writes", "checkpoint_blobs"):
            try:
                conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (conversation_id,))
            except Exception:
                continue
        try:
            conn.commit()
        except Exception:
            pass

    saver.delete_thread = delete_thread
    return saver


def _exists(saver, conversation_id: str) -> bool:
    config = {"configurable": {"thread_id": conversation_id}}
    getter = getattr(saver, "get_tuple", None) or getattr(saver, "get", None)
    if getter is None:
        return False
    try:
        return getter(config) is not None
    except Exception:
        return False


def get_checkpointer(settings: Settings):
    path = Path(settings.checkpoint_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    return protect_checkpointer(saver)
