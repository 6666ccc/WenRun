from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from loguru import logger

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.api.routes import chat, health
from app.core.logging import (
    configure_logging,
    new_request_id,
    reset_request_id,
    set_request_id,
)

configure_logging()


def create_app() -> FastAPI:
    """创建温润 AI HTTP 服务。"""
    app = FastAPI(title="WenRun AI API", version="0.1.0")
    app.include_router(chat.router)
    app.include_router(health.router)

    @app.middleware("http")
    async def request_trace(request: Request, call_next):
        request_id = new_request_id(request.headers.get("X-Request-Id"))
        token = set_request_id(request_id)
        started_at = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            duration_ms = int((perf_counter() - started_at) * 1000)
            logger.info(
                "http_request request_id={} method={} path={} status={} duration_ms={}",
                request_id, request.method, request.url.path, status_code, duration_ms,
            )
            reset_request_id(token)

    return app


app = create_app()
