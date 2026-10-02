"""Deterministic quality report rules for ingestion review and publication."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Sequence

from .models import (
    Chunk,
    ElementType,
    ParsedDocument,
    QualityIssue,
    QualityReport,
    QualityStatus,
)

_TABLE_OVERSIZED_PART_LIMIT = 3
_SCANNED_TEXT_COVERAGE = 0.5
_STRUCTURE_PAGE_LIMIT = 5
_RESIDUE_MAX_LENGTH = 24
_SENTENCE_END = ("。", "！", "？", ".", "!", "?")
_DIGITS = re.compile(r"\d+")
_PDF_TOKEN = re.compile(r"[=+\-*/×÷]|[A-Za-z]+|\d+|[\u3400-\u9fff]")


def assess_quality(
    parsed: ParsedDocument,
    cleaned: ParsedDocument,
    chunk_count: int,
    chunks: Sequence[Chunk] | None = None,
) -> QualityReport:
    """Assess known extraction gaps without inventing parser confidence scores."""

    issues: list[QualityIssue] = []
    metadata = parsed.metadata
    coverage = metadata.get("pdf_coverage")
    if isinstance(coverage, dict):
        for page_number in coverage.get("missing_text_page_numbers", []):
            issues.append(
                QualityIssue(
                    code="pdf_page_without_extracted_text",
                    severity="error",
                    blocking=True,
                    message="This PDF page has no extracted text and needs OCR or review.",
                    page_number=int(page_number),
                    details={
                        "ocr_applied": bool(coverage.get("ocr_applied", False)),
                        "has_text_layer": False,
                    },
                )
            )
        text_coverage = coverage.get("text_coverage")
        if isinstance(text_coverage, (int, float)) and text_coverage < _SCANNED_TEXT_COVERAGE:
            issues.append(
                QualityIssue(
                    code="pdf_scanned_document",
                    severity="error",
                    blocking=True,
                    message="请上传电子版 PDF 或 Word 原件",
                    details={
                        "text_coverage": text_coverage,
                        "threshold": _SCANNED_TEXT_COVERAGE,
                    },
                )
            )
        page_count = coverage.get("page_count")
        has_heading = any(
            element.element_type in {ElementType.TITLE, ElementType.HEADING}
            for element in cleaned.elements
        )
        if (
            parsed.source_type == "pdf"
            and isinstance(page_count, int)
            and page_count > _STRUCTURE_PAGE_LIMIT
            and not has_heading
        ):
            issues.append(
                QualityIssue(
                    code="pdf_no_structure",
                    severity="warning",
                    blocking=False,
                    message="章节结构缺失，检索效果可能较差",
                    details={"page_count": page_count},
                )
            )

    searchable = [
        element
        for element in cleaned.elements
        if (element.search_text or "").strip()
        and element.element_type not in {ElementType.HEADER, ElementType.FOOTER}
    ]
    content_elements = [
        element
        for element in searchable
        if element.element_type
        not in {ElementType.TITLE, ElementType.HEADING, ElementType.CAPTION}
    ]
    if not content_elements:
        issues.append(
            QualityIssue(
                code="no_searchable_content",
                severity="error",
                blocking=True,
                message="No searchable body content was produced; assets remain available for review.",
                details={
                    "asset_only_elements": sum(
                        bool(item.asset_refs) for item in cleaned.elements
                    )
                },
            )
        )
    if not chunk_count and content_elements:
        issues.append(
            QualityIssue(
                code="no_retrieval_chunks",
                severity="error",
                blocking=True,
                message="Searchable content did not produce any retrieval chunks.",
            )
        )

    for element in cleaned.elements:
        if element.element_type == ElementType.TABLE and element.structured_table is None:
            issues.append(
                QualityIssue(
                    code="table_structure_unavailable",
                    severity="warning",
                    blocking=False,
                    message="Table text is available, but row/cell structure could not be confirmed.",
                    element_id=element.element_id,
                    page_number=element.page_number,
                )
            )
        if element.element_type == ElementType.FORMULA and element.metadata.get("latex_fallback"):
            issues.append(
                QualityIssue(
                    code="formula_conversion_fallback",
                    severity="warning",
                    blocking=False,
                    message="公式可能显示异常，建议人工核对",
                    element_id=element.element_id,
                    page_number=element.page_number,
                )
            )

    if chunks:
        issues.extend(_chunk_issues(parsed, chunks))

    confidence_unknown = sum(element.confidence is None for element in parsed.elements)
    metrics = {
        "element_count": len(parsed.elements),
        "searchable_element_count": len(searchable),
        "chunk_count": chunk_count,
        "unknown_confidence_count": confidence_unknown,
        "asset_reference_count": sum(len(item.asset_refs) for item in parsed.elements),
        "pdf_page_count": coverage.get("page_count") if isinstance(coverage, dict) else None,
        "pdf_text_coverage": coverage.get("text_coverage") if isinstance(coverage, dict) else None,
    }
    if any(issue.blocking for issue in issues):
        status = QualityStatus.BLOCKED
    elif any(issue.severity in {"warning", "error"} for issue in issues):
        status = QualityStatus.REVIEW
    else:
        status = QualityStatus.PASS
    return QualityReport(status=status, issues=issues, metrics=metrics)


def _chunk_issues(parsed: ParsedDocument, chunks: Sequence[Chunk]) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    protected = _protected_lines(chunks)
    residue_counts: Counter[str] = Counter()
    for chunk in chunks:
        section_lines = {_normalize_line(part) for part in chunk.section_path if part.strip()}
        for line in _edge_lines(chunk.text):
            normalized = _normalize_line(line)
            if not normalized or normalized in protected or normalized in section_lines:
                continue
            if len(normalized) > _RESIDUE_MAX_LENGTH or normalized.endswith(_SENTENCE_END):
                continue
            if "，" in normalized or "," in normalized:
                continue
            residue_counts[normalized] += 1
    for line, count in residue_counts.most_common(5):
        if count < 2:
            continue
        issues.append(
            QualityIssue(
                code="header_footer_residue",
                severity="warning",
                blocking=False,
                message="可能有未剔除的页眉页脚",
                details={"line": line, "chunk_count": count},
            )
        )

    parts_by_table: dict[str, int] = defaultdict(int)
    for chunk in chunks:
        table_id = str(chunk.metadata.get("table_element_id") or "")
        part_count = chunk.metadata.get("table_part_count") or 0
        if table_id and isinstance(part_count, int):
            parts_by_table[table_id] = max(parts_by_table[table_id], part_count)
    for table_id, part_count in parts_by_table.items():
        if part_count > _TABLE_OVERSIZED_PART_LIMIT:
            issues.append(
                QualityIssue(
                    code="table_oversized",
                    severity="info",
                    blocking=False,
                    message="大表格已拆分，确认每段表头正确",
                    element_id=table_id,
                    details={"part_count": part_count, "limit": _TABLE_OVERSIZED_PART_LIMIT},
                )
            )

    if parsed.source_type == "pdf":
        for chunk in chunks:
            if _looks_like_garbled_formula(chunk.text):
                issues.append(
                    QualityIssue(
                        code="formula_garbled_suspected",
                        severity="warning",
                        blocking=False,
                        message="疑似公式乱码，建议提供 Word 原件",
                        page_number=chunk.page_numbers[0] if chunk.page_numbers else None,
                    )
                )
                break
    return issues


def _protected_lines(chunks: Sequence[Chunk]) -> set[str]:
    protected: set[str] = set()
    for chunk in chunks:
        raw = chunk.metadata.get("table_header_lines") or ""
        if not isinstance(raw, str):
            continue
        for line in raw.splitlines():
            normalized = _normalize_line(line)
            if normalized:
                protected.add(normalized)
    return protected


def _edge_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    edges = [lines[0]]
    if len(lines) > 1:
        edges.append(lines[-1])
    return edges


def _normalize_line(line: str) -> str:
    return _DIGITS.sub("#", " ".join(line.split()))


def _looks_like_garbled_formula(text: str) -> bool:
    tokens = _PDF_TOKEN.findall(text)
    if len(tokens) < 12:
        return False
    isolated = [
        token
        for token in tokens
        if token in set("=+-*/×÷") or (len(token) == 1 and token.isascii() and token.isalpha())
    ]
    return len(isolated) / len(tokens) >= 0.45
