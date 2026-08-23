from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from langchain_core.messages import HumanMessage
from loguru import logger
from starlette.concurrency import run_in_threadpool

from app.api.dependencies.auth import verify_api_key
from app.graphs.hospital.graphs import graph
from app.models.chat import ChatRequest, ChatResponse
from app.rag.ingest import ingest_file

router = APIRouter(
    prefix="/v1/chat",
    tags=["Chat"],
    dependencies=[Depends(verify_api_key)],
)


def _not_implemented() -> None:
    raise HTTPException(
        status_code=501,
        detail="AI 对话能力尚未实现；当前模块仅保留服务骨架。",
    )


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """执行医院对话图，并返回本轮的最终回复和 RAG 来源。"""
    initial_state = {
        "messages": [HumanMessage(content=request.message)],
        "conversation_id": request.conversation_id,
        "patient_id": request.user_context.patient_id,
    }

    try:
        # 图中的检索和模型调用均为同步 I/O，放到工作线程避免阻塞 FastAPI 事件循环。
        result = await run_in_threadpool(graph.invoke, initial_state)
    except Exception as exc:
        logger.exception("chat_graph_failed conversation_id={}", request.conversation_id)
        raise HTTPException(status_code=500, detail="AI 对话处理失败，请稍后再试") from exc

    reply = result.get("final_reply")
    if not isinstance(reply, str) or not reply.strip():
        logger.error("chat_graph_missing_final_reply conversation_id={}", request.conversation_id)
        raise HTTPException(status_code=500, detail="AI 对话未生成有效回复")

    selected_agents: list[str] = []
    for agent_name in result.get("selected_agents") or []:
        if isinstance(agent_name, str):
            selected_agents.append(agent_name)

    sources: list[dict[str, Any]] = []
    for source in result.get("rag_sources") or []:
        if isinstance(source, dict):
            sources.append(source)

    return ChatResponse(
        reply=reply.strip(),
        conversation_id=request.conversation_id,
        selected_agents=selected_agents,
        sources=sources,
    )


@router.post("/test")
async def test_chat() -> None:
    _not_implemented()


# 步骤一：接收用户上传的 PDF、Word、TXT 或 Markdown 文件。
# 步骤二：在工作线程中调用 ingest_file，完成解析、分块、Embedding 和写入 Qdrant。
# 步骤三：返回文档 ID 和分块数量，方便使用 curl 或 Swagger UI 验证 RAG 是否已经入库。
@router.post("/knowledge/upload")
async def upload_knowledge_document(file: UploadFile = File(...)) -> dict:  # noqa: B008
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="上传文件缺少文件名")

    # 测试接口限制单个文件大小为 50 MB，避免一次请求占用过多内存。
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 50 MB")

    try:
        # ingest_file 中包含同步的文件解析和网络 Embedding 调用，不能阻塞事件循环。
        result = await run_in_threadpool(ingest_file, data, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("knowledge_upload_failed filename={}", filename)
        raise HTTPException(status_code=500, detail="文档处理失败，请检查服务日志") from exc

    return {
        "success": True,
        "message": "文档已解析并写入知识库",
        "data": result,
    }


@router.post("/resume/stream")
async def resume_stream() -> None:
    _not_implemented()


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> None:
    _not_implemented()
