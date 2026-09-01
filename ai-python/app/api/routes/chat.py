import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from loguru import logger
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from app.api.dependencies.auth import DelegationContext, verify_api_key, verify_delegation_token
from app.core.logging import current_request_id
from app.graphs.hospital.graphs import graph
from app.models.chat import ChatRequest, ChatResponse
from app.rag.ingest import ingest_file

router = APIRouter(
    prefix="/v1/chat",
    tags=["Chat"],
    dependencies=[Depends(verify_api_key)],
)


def _response_from_state(request: ChatRequest, result: dict[str, Any]) -> ChatResponse:
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


def _initial_state(request: ChatRequest, delegation: DelegationContext) -> dict[str, Any]:
    return {
        "messages": [HumanMessage(content=request.message)],
        "conversation_id": request.conversation_id,
        "patient_id": request.user_context.patient_id,
        # 当前图没有 checkpointer；如后续加入持久化，必须改用 Runtime Context，
        # 不能把委托 Token 写入可恢复的 State。
        "delegated_token": delegation.token,
        "request_id": current_request_id(),
    }


def _text_from_message_chunk(message_chunk: object) -> str:
    """从 LangChain 字符串或内容块消息片段中提取文本。"""

    content = getattr(message_chunk, "content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    text_parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            value = block.get("text")
        else:
            value = getattr(block, "text", None)
        if isinstance(value, str):
            text_parts.append(value)
    return "".join(text_parts)


def _is_streamable_message(message_chunk: object) -> bool:
    """判断图消息是否可以安全地作为面向患者的文本公开。

    LangGraph 在流式传输时可能会暴露嵌套 Agent 产生的消息。知识 Agent
    可能会在生成最终答案之前产生工具结果、路由消息和工具调用请求。
    只有助手文本属于公开 SSE 协议的一部分，其余内容都属于图的内部状态。
    """

    if not isinstance(message_chunk, (AIMessage, AIMessageChunk)):
        return False
    if getattr(message_chunk, "tool_calls", None):
        return False
    if getattr(message_chunk, "tool_call_chunks", None):
        return False
    if getattr(message_chunk, "invalid_tool_calls", None):
        return False
    return bool(_text_from_message_chunk(message_chunk).strip())


def _stream_visible_nodes(selected_agents: list[str]) -> set[str]:
    """选择对患者可见的图节点输出。

    起始节点也可能产生 LLM 消息，但这些是路由 JSON，绝不能发送到浏览器。
    当多个回复节点同时启用时，只有 final_node 执行最终汇总，因此它是唯一安全的流式输出节点。
    """

    # 知识 Agent 可能会调用 RAG 和网页搜索工具。其嵌套模型消息属于实现细节，
    # 因此知识请求必须等待图完成最终汇总。仅闲聊请求没有检索或工具阶段，
    # 可以继续直接从 chat 节点进行流式输出。
    if selected_agents == ["chat"]:
        return {"chat_node"}
    return {"final_node"}


def _is_visible_message_node(
    node_name: object,
    namespace: object,
    visible_nodes: set[str],
) -> bool:
    """仅匹配可见节点或其明确允许的模型子图。"""

    if isinstance(node_name, str) and node_name in visible_nodes:
        return True

    if not isinstance(namespace, (list, tuple)):
        return False

    # chat/final 节点可能包含嵌套的模型调用。只有命名空间的第一段可以授予可见性；
    # knowledge 节点下的工具等更深层级的同级节点绝不能继承该可见性。
    first_segment = namespace[0] if namespace else None
    if not isinstance(first_segment, str):
        return False
    first_node = first_segment.split(":", 1)[0]
    return first_node in visible_nodes


def _merge_stream_state(state: dict[str, Any], part: dict[str, Any]) -> None:
    """从根图的 v2 values 事件中保留最新图状态。"""

    # 嵌套 Agent 有自己的 values 流。只有根图的 values 包含此 API 所需的
    # final_reply、selected_agents 和 rag_sources。
    if part.get("ns") or part.get("type") != "values":
        return
    data = part.get("data")
    if isinstance(data, dict):
        state.update(data)


async def _stream_graph(
    request: ChatRequest, delegation: DelegationContext
) -> AsyncIterator[dict[str, Any]]:
    """生成 LangGraph v2 流式片段。"""

    initial_state = _initial_state(request, delegation)
    async for part in graph.astream(
        initial_state,
        stream_mode=["messages", "values"],
        subgraphs=True,
        version="v2",
    ):
        if isinstance(part, dict):
            yield part


def _sse(event: dict[str, Any]) -> str:
    """编码一条兼容浏览器的服务器发送事件，同时保留中文文本。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_knowledge_document(
    file: UploadFile = File(..., description="用于构建知识库的 PDF、Word 或文本文件"),
) -> dict[str, str | int]:
    """上传文档并写入医院 RAG 知识库。"""

    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail="请上传带文件名的文档")

    try:
        content = await file.read()
    finally:
        await file.close()

    if not content:
        raise HTTPException(status_code=400, detail="上传文件不能为空")

    try:
        return await run_in_threadpool(ingest_file, content, filename)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("knowledge_document_ingest_failed filename={}", filename)
        raise HTTPException(status_code=500, detail="文档写入知识库失败，请稍后再试") from exc


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> StreamingResponse:
    """运行对话图，并通过 SSE 暴露增量模型输出。"""

    async def events() -> AsyncIterator[str]:
        yield _sse({"type": "status", "content": "正在分析您的问题…"})
        graph_state: dict[str, Any] = {}
        streamed_reply = False
        selected_agents: list[str] = []
        retrieval_status_sent = False
        final_status_sent = False
        try:
            async for part in _stream_graph(request, delegation):
                _merge_stream_state(graph_state, part)
                incoming_agents = graph_state.get("selected_agents") or []
                selected_agents = [
                    agent for agent in incoming_agents if isinstance(agent, str)
                ]

                if "knowledge" in selected_agents and not retrieval_status_sent:
                    retrieval_status_sent = True
                    yield _sse({"type": "status", "content": "正在检索相关资料…"})

                if part.get("type") != "messages":
                    continue
                data = part.get("data")
                if not isinstance(data, (list, tuple)) or len(data) != 2:
                    continue
                message_chunk, metadata = data
                if not isinstance(metadata, dict):
                    continue
                node_name = metadata.get("langgraph_node")
                visible_nodes = _stream_visible_nodes(selected_agents)
                namespace = part.get("ns") or ()
                if not _is_visible_message_node(node_name, namespace, visible_nodes):
                    continue
                if not _is_streamable_message(message_chunk):
                    continue
                content = _text_from_message_chunk(message_chunk)
                if content:
                    if "knowledge" in selected_agents and not final_status_sent:
                        final_status_sent = True
                        yield _sse({"type": "status", "content": "正在整理答案…"})
                    streamed_reply = True
                    yield _sse({"type": "token", "content": content})

            response = _response_from_state(request, graph_state)
        except HTTPException as exc:
            yield _sse({
                "type": "error",
                "code": "AI_CHAT_FAILED",
                "message": str(exc.detail),
            })
            return
        except asyncio.CancelledError:
            logger.info("chat_stream_cancelled conversation_id={}", request.conversation_id)
            raise
        except Exception:
            logger.exception("chat_stream_failed conversation_id={}", request.conversation_id)
            yield _sse({
                "type": "error",
                "code": "AI_CHAT_FAILED",
                "message": "AI 对话处理失败，请稍后再试",
            })
            return

        for source in response.sources:
            yield _sse({"type": "citation", "sources": [source]})
        if not streamed_reply:
            # 如果服务提供方不提供令牌片段，则发送一个完整令牌以保持协议一致，
            # 避免返回空答案。
            yield _sse({"type": "token", "content": response.reply})
        yield _sse({
            "type": "done",
            **response.model_dump(by_alias=True),
        })

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
