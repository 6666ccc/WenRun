"""公开网页搜索工具，供知识节点和快速模式查询院外资料。"""

import os

from langchain.tools import tool
from tavily import TavilyClient
from loguru import logger
from app.observability.progress import track_operation


def format_search_results(results: list[dict]) -> str:
    """把标题、链接和摘要整理成模型可引用的文本。"""
    blocks: list[str] = []
    for index, item in enumerate(results, start=1):
        title = str(item.get("title") or "未命名来源").strip()
        url = str(item.get("url") or "").strip()
        content = str(item.get("content") or "").strip()
        blocks.append(f"[{index}] {title}\n链接: {url}\n摘要: {content}")
    return "\n\n".join(blocks)


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """调用 Tavily；未配置密钥时返回空结果，让上层给出明确提示。"""
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        return []

    data = TavilyClient(api_key=api_key).search(
        query,
        max_results=max_results,
        search_depth="basic",
        timeout=20,
    )
    mapped: list[dict] = []
    for item in data.get("results") or []:
        mapped.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "content": item.get("content") or "",
            }
        )
    return mapped


@tool
@track_operation("web")
def web_search(query: str) -> str:
    """检索公开网页。query 必须是整理后的短检索词，不要传入患者原话全文。"""
    try:
        text = format_search_results(search_web(query))
    except Exception as exc:  # Provider/network failure must not discard sibling search results.
        logger.warning("Public search unavailable: {}", type(exc).__name__)
        return "暂时无法查询公开医疗资料。本次不要重复尝试同一检索；可依据其他成功检索的资料回答，没有依据时请明确说明。"
    return text or "（无命中。可能未配置 TAVILY_API_KEY，或搜索无结果。）"
