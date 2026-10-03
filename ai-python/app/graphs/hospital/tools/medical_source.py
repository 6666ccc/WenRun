"""Read source text from controlled public authorities; snippets are discovery only."""

import os
from urllib.parse import urlsplit

from langchain.tools import tool
from tavily import TavilyClient

from app.graphs.hospital.context_builder import (
    ContextBudgetError,
    bounded_external_context,
)
from app.rag.safety import has_prompt_injection_risk

AUTHORITIES = (
    "nmpa.gov.cn",
    "cde.org.cn",
    "nhc.gov.cn",
    "who.int",
    "fda.gov",
    "ema.europa.eu",
    "nice.org.uk",
    "cdc.gov",
    "nhs.uk",
)


def is_authoritative_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and not parsed.username
        and port in (None, 443)
        and any(host == domain or host.endswith("." + domain) for domain in AUTHORITIES)
    )


def fetch_medical_source(url: str) -> str | None:
    if not is_authoritative_url(url) or not os.getenv("TAVILY_API_KEY"):
        return None
    data = TavilyClient(api_key=os.environ["TAVILY_API_KEY"]).extract(urls=[url])
    for item in data.get("results") or []:
        # Require the returned URL to match the authorized source; no redirect promotion.
        text = str(item.get("raw_content") or "").strip()
        if item.get("url") != url or not text or has_prompt_injection_risk(text):
            continue
        try:
            return bounded_external_context(
                "authoritative_medical_source",
                {
                    "url": url,
                    "content": text,
                    "sourceKind": "authority_source_text",
                    "instruction": "核对资料是否为适用指南或正式说明书；权威域名本身不代表适用。",
                },
            ).content
        except ContextBudgetError:
            # Never cut out contraindications or qualification paragraphs to fit.
            return None
    return None


@tool
def read_medical_source(url: str) -> str:
    """读取权威专业来源正文；搜索摘要不能作为个性化用药结论的依据。"""
    try:
        return (
            fetch_medical_source(url)
            or "没有取得可用的可靠资料正文，不能据此输出个性化结论。"
        )
    except Exception:  # noqa: BLE001 - provider failure supplies no usable evidence
        return "可靠资料正文暂时无法读取，不能据此输出个性化结论。"
