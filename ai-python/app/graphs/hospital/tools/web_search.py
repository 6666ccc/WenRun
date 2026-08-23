import os

from langchain.tools import tool
from tavily import TavilyClient


def format_search_results(results: list[dict]) -> str:
    blocks: list[str] = []
    for index, item in enumerate(results, start=1):
        title = str(item.get("title") or "未命名来源").strip()
        url = str(item.get("url") or "").strip()
        content = str(item.get("content") or "").strip()
        blocks.append(f"[{index}] {title}\n链接: {url}\n摘要: {content}")
    return "\n\n".join(blocks)


def search_web(query: str, max_results: int = 5) -> list[dict]:
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        return []

    data = TavilyClient(api_key=api_key).search(
        query,
        max_results=max_results,
        search_depth="basic",
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
def web_search(query: str) -> str:
    """检索公开网页。query 必须是整理后的短检索词，不要传入患者原话全文。"""
    text = format_search_results(search_web(query))
    return text or "（无命中。可能未配置 TAVILY_API_KEY，或搜索无结果。）"
