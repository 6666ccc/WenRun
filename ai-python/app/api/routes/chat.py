from fastapi import APIRouter
from app.models.chat import ChatRequest, ChatResponse
from app.graphs.hospital.graph import run_graph

router = APIRouter(prefix="/v1", tags=["Chat"])


@router.post("/chat")
def chat(request: ChatRequest) -> ChatResponse:
  return ChatResponse(reply=run_graph(request.message))