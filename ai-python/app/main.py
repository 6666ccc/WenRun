"""启动 Python HTTP 服务：注册接口、连接会话检查点、给每个请求记录追踪号。"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from loguru import logger

# 部分下游模块导入时就会创建模型，必须先把本项目的环境变量读进来。
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.api.routes import chat, health, knowledge, metrics
from app.core.logging import (
    configure_logging,
    new_request_id,
    reset_request_id,
    set_request_id,
)
from app.graphs.hospital.checkpointing import memory_lifespan

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务启动时建立可恢复的会话图；关闭时释放检查点连接。"""
    async with memory_lifespan() as saver:
        production = os.getenv("RAG_ENVIRONMENT", "development").lower() == "production"
        if production and saver is None:
            raise RuntimeError("Production requires a working Redis checkpointer")
        worker = None
        try:
            from app.rag.lifecycle import get_rag_service

            worker = get_rag_service()
            worker.ensure_ready()
            worker.start_worker()
        except Exception:
            logger.exception("rag_lifecycle_worker_not_started")
            if production:
                raise
        app.state.rag_worker = worker
        try:
            yield
        finally:
            if worker is not None:
                worker.stop_worker()


def create_app() -> FastAPI:
    """创建温润 AI HTTP 服务。"""
    production = os.getenv("RAG_ENVIRONMENT", "development").lower() == "production"
    app = FastAPI(
        title="WenRun AI API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )
    app.include_router(chat.router)
    app.include_router(knowledge.router)
    app.include_router(health.router)
    app.include_router(metrics.router)

    @app.middleware("http")
    async def request_trace(request: Request, call_next):
        # 同一个请求号贯穿 Python 日志，并原样回给调用方，方便跨 Java/Python 查问题。
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
            # 即使接口报错，也记录耗时并清理当前请求的上下文，避免串到下一个请求。
            duration_ms = int((perf_counter() - started_at) * 1000)
            logger.info(
                "http_request request_id={} method={} path={} status={} duration_ms={}",
                request_id,
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )
            reset_request_id(token)

    return app


app = create_app()
