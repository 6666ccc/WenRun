from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.api.routes import chat, health, knowledge
from app.core.logging import configure_logging
from app.services.chat_service import ChatServiceError

configure_logging()

app = FastAPI(
    title="WenRun AI API",
    version="0.1.0",
)

app.include_router(chat.router)
app.include_router(health.router)
app.include_router(knowledge.router)


@app.exception_handler(ChatServiceError)
async def handle_chat_service_error(_request: Request, exc: ChatServiceError) -> JSONResponse:
    status = 409
    if exc.code == "INTERRUPT_CONVERSATION_MISMATCH":
        status = 403
    return JSONResponse(status_code=status, content={"code": exc.code, "message": exc.message})
