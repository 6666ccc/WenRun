from app.models.sse import ChatStreamEvent


def encode_sse(event: ChatStreamEvent) -> str:
    return f"data: {event.model_dump_json(by_alias=True, exclude_none=True)}\n\n"
