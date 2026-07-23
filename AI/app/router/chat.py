from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse
from app.agent.graph.workflow import run_graph

router = APIRouter(prefix="/v1", tags=["Chat"])


@router.post("/chat")
def chat(request: ChatRequest) -> ChatResponse:
  return ChatResponse(reply=run_graph(request.message))