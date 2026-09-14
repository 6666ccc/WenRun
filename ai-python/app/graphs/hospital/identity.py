"""Pure identity helpers shared by the API and deterministic safety evaluation."""


def thread_id_for(user_id: int, conversation_id: str) -> str:
    """Namespace every caller-controlled conversation ID by verified user identity."""

    return f"user:{user_id}:conversation:{conversation_id}"
