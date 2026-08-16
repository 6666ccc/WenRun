from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse

from app.api.dependencies.auth import verify_api_key
from app.api.dependencies.runtime import ToolRuntimeContext, get_tool_context
from app.models.chat import ChatRequest, ChatResponse, ResumeRequest
from app.services.chat_service import ChatService, get_chat_service
from app.services.sse import encode_sse


router = APIRouter(
    prefix="/v1/chat",
    tags=["Chat"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
    runtime: ToolRuntimeContext = Depends(get_tool_context),
) -> ChatResponse:
    return await service.invoke_chat(request, runtime)


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
    runtime: ToolRuntimeContext = Depends(get_tool_context),
) -> StreamingResponse:
    return StreamingResponse(
        (encode_sse(event) async for event in service.stream_chat(request, runtime)),
        media_type="text/event-stream",
    )


@router.post("/resume/stream")
async def resume_stream(
    request: ResumeRequest,
    service: ChatService = Depends(get_chat_service),
    runtime: ToolRuntimeContext = Depends(get_tool_context),
) -> StreamingResponse:
    return StreamingResponse(
        (encode_sse(event) async for event in service.resume_stream(request, runtime)),
        media_type="text/event-stream",
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: str,
    service: ChatService = Depends(get_chat_service),
) -> Response:
    await service.delete_conversation(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)