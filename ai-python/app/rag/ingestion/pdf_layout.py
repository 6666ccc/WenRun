"""用 pypdf 已经提供的坐标和字号整理 PDF 正文。

页眉页脚要同时满足位置和跨页重复才会剔除。标题靠字号和常见编号识别。
上一页没有句号结尾、下一页开头又不是标题时，把两段合成一段。
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .models import ElementType, ParsedElement, SourceProvenance

_MARGIN_RATIO = 0.06
_HEADING_SIZE_RATIO = 1.15
_PARAGRAPH_GAP_RATIO = 1.8
_HEADING_PATTERNS = (
    (1, re.compile(r"^第[0-9０-９一二三四五六七八九十百千]+[章节篇部]")),
    (2, re.compile(r"^[一二三四五六七八九十]+、")),
    (3, re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:\s+|$)")),
    (2, re.compile(r"^[0-9]+\.[0-9]+(?:\s+|$)")),
    (2, re.compile(r"^[0-9]+[.、](?:\s+|$)")),
)
_SENTENCE_END = re.compile(r"[。！？!?]$")
_DIGITS = re.compile(r"\d+")
_WHITESPACE = re.compile(r"\s+")


@dataclass(slots=True)
class PdfTextRun:
    """visitor_text 回调拿到的一小段文字及其版面位置。"""

    text: str
    page_number: int
    x: float
    y: float
    font_size: float
    page_width: float
    page_height: float
    bold: bool = False


@dataclass(slots=True)
class PdfTextLine:
    """同一行上合并后的文字。y 使用 PDF 默认的左下角原点。"""

    text: str
    page_number: int
    x: float
    y: float
    font_size: float
    page_width: float
    page_height: float
    bold: bool = False
    char_count: int = 0
    size_counts: Counter[float] = field(default_factory=Counter)


def extract_text_runs(page: object, page_number: int) -> list[PdfTextRun]:
    """读取一页文字。visitor 没有结果时，退回按空行拆分的纯文本。"""

    box = getattr(page, "mediabox", None)
    width = float(getattr(box, "width", 0) or 0)
    height = float(getattr(box, "height", 0) or 0)
    runs: list[PdfTextRun] = []

    def visitor(text: object, cm: object, tm: object, font: object, font_size: object) -> None:
        value = str(text or "").replace("\n", "").strip()
        if not value:
            return
        x, y, size = _position(cm, tm, font_size)
        runs.append(
            PdfTextRun(
                text=value,
                page_number=page_number,
                x=x,
                y=y,
                font_size=size if size > 0 else 12.0,
                page_width=width,
                page_height=height,
                bold=_is_bold(font),
            )
        )

    plain = page.extract_text(visitor_text=visitor) or ""
    if runs:
        return runs
    if not str(plain).strip():
        return []
    return [
        PdfTextRun(
            text=block.strip(),
            page_number=page_number,
            x=0,
            y=height / 2 if height else 0,
            font_size=12,
            page_width=width,
            page_height=height,
        )
        for block in re.split(r"\n\s*\n", str(plain))
        if block.strip()
    ]


def elements_from_lines(lines: list[PdfTextLine]) -> list[ParsedElement]:
    """把已经合并好的行变成标题、正文和页眉页脚元素。"""

    ordered = sorted(lines, key=lambda line: (line.page_number, -line.y, line.x))
    furniture = _furniture_keys(ordered)
    body_size = _body_font_size(ordered, furniture)
    heading_levels = _heading_levels(ordered, furniture, body_size)
    return _merge_cross_page_paragraphs(
        _blocks_to_elements(ordered, furniture, body_size, heading_levels)
    )


def elements_from_runs(runs: list[PdfTextRun]) -> list[ParsedElement]:
    return elements_from_lines(_cluster_lines(runs))


def _cluster_lines(runs: list[PdfTextRun]) -> list[PdfTextLine]:
    ordered = sorted(runs, key=lambda run: (run.page_number, -round(run.y, 1), run.x))
    lines: list[PdfTextLine] = []
    line_ends: list[float] = []
    for run in ordered:
        if (
            lines
            and lines[-1].page_number == run.page_number
            and abs(lines[-1].y - run.y) <= 2.5
        ):
            gap = run.x - line_ends[-1]
            joiner = " " if gap > max(run.font_size, 1) * 0.6 else ""
            current = lines[-1]
            current.text = f"{current.text}{joiner}{run.text}"
            current.bold = current.bold or run.bold
            current.char_count += len(run.text)
            current.size_counts[round(run.font_size, 1)] += len(run.text)
            current.font_size = current.size_counts.most_common(1)[0][0]
            line_ends[-1] = max(line_ends[-1], run.x + len(run.text) * run.font_size * 0.45)
            continue
        size = round(run.font_size, 1)
        lines.append(
            PdfTextLine(
                text=run.text,
                page_number=run.page_number,
                x=run.x,
                y=run.y,
                font_size=size,
                page_width=run.page_width,
                page_height=run.page_height,
                bold=run.bold,
                char_count=len(run.text),
                size_counts=Counter({size: len(run.text)}),
            )
        )
        line_ends.append(run.x + max(len(run.text), 1) * run.font_size * 0.45)
    return lines


def _position(cm: object, tm: object, font_size: object) -> tuple[float, float, float]:
    current = _matrix(cm)
    text = _matrix(tm)
    x = current[0] * text[4] + current[2] * text[5] + current[4]
    y = current[1] * text[4] + current[3] * text[5] + current[5]
    y_scale = abs(current[1] * text[2] + current[3] * text[3])
    if y_scale < 1e-6:
        y_scale = 1.0
    try:
        size = float(font_size) * y_scale
    except (TypeError, ValueError):
        size = 0.0
    return x, y, size


def _matrix(value: object) -> list[float]:
    try:
        numbers = [float(item) for item in list(value)[:6]]  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    if len(numbers) < 6:
        return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    return numbers


def _is_bold(font: object) -> bool:
    if font is None or not hasattr(font, "get"):
        return False
    try:
        name = str(font.get("/BaseFont") or "")
    except (TypeError, AttributeError):
        return False
    folded = name.casefold()
    return "bold" in folded or "black" in folded


def _zone(line: PdfTextLine) -> str:
    if line.page_height <= 0:
        return "body"
    ratio = line.y / line.page_height
    if ratio >= 1 - _MARGIN_RATIO:
        return "header"
    if ratio <= _MARGIN_RATIO:
        return "footer"
    return "body"


def _normalize_repeated_text(text: str) -> str:
    collapsed = _WHITESPACE.sub(" ", text).strip()
    return _DIGITS.sub("#", collapsed)


def _furniture_keys(lines: list[PdfTextLine]) -> set[tuple[str, str]]:
    pages_by_key: dict[tuple[str, str], set[int]] = defaultdict(set)
    for line in lines:
        zone = _zone(line)
        if zone == "body" or not line.text.strip():
            continue
        pages_by_key[(zone, _normalize_repeated_text(line.text))].add(line.page_number)
    page_count = len({line.page_number for line in lines})
    return {
        key
        for key, pages in pages_by_key.items()
        if len(pages) >= 2 and len(pages) > page_count / 2
    }


def _is_furniture(line: PdfTextLine, furniture: set[tuple[str, str]]) -> bool:
    zone = _zone(line)
    if zone == "body":
        return False
    return (zone, _normalize_repeated_text(line.text)) in furniture


def _body_font_size(lines: list[PdfTextLine], furniture: set[tuple[str, str]]) -> float:
    counts: Counter[float] = Counter()
    for line in lines:
        if _is_furniture(line, furniture):
            continue
        counts[round(line.font_size, 1)] += max(len(line.text), 1)
    if not counts:
        return 12.0
    return counts.most_common(1)[0][0]


def _pattern_level(text: str) -> int | None:
    for level, pattern in _HEADING_PATTERNS:
        if pattern.match(text):
            return level
    return None


def _heading_level(
    line: PdfTextLine,
    body_size: float,
    size_levels: dict[float, int],
) -> int | None:
    text = line.text.strip()
    if not text or len(text) > 40 or _SENTENCE_END.search(text):
        return None
    size = round(line.font_size, 1)
    by_size = size_levels.get(size)
    if by_size and size >= body_size * _HEADING_SIZE_RATIO:
        return by_size
    by_pattern = _pattern_level(text)
    if by_pattern and len(text) <= 30:
        return by_pattern
    return None


def _heading_levels(
    lines: list[PdfTextLine],
    furniture: set[tuple[str, str]],
    body_size: float,
) -> dict[float, int]:
    sizes = {
        round(line.font_size, 1)
        for line in lines
        if not _is_furniture(line, furniture)
        and line.text.strip()
        and len(line.text.strip()) <= 40
        and not _SENTENCE_END.search(line.text.strip())
        and round(line.font_size, 1) >= body_size * _HEADING_SIZE_RATIO
    }
    levels: dict[float, int] = {}
    for index, size in enumerate(sorted(sizes, reverse=True)):
        levels[size] = min(index + 1, 3)
    return levels


def _join_lines(parts: list[str]) -> str:
    text = ""
    for part in parts:
        value = part.strip()
        if not value:
            continue
        if not text:
            text = value
            continue
        if (
            text[-1].isascii()
            and text[-1].isalnum()
            and value[0].isascii()
            and value[0].isalnum()
        ):
            text = f"{text} {value}"
        else:
            text = f"{text}{value}"
    return text.strip()


def _blocks_to_elements(
    lines: list[PdfTextLine],
    furniture: set[tuple[str, str]],
    body_size: float,
    size_levels: dict[float, int],
) -> list[ParsedElement]:
    elements: list[ParsedElement] = []
    paragraph: list[PdfTextLine] = []
    emitted_body = False

    def flush_paragraph() -> None:
        nonlocal emitted_body
        if not paragraph:
            return
        text = _join_lines([line.text for line in paragraph])
        if text:
            elements.append(_element(ElementType.PARAGRAPH, text, paragraph, len(elements)))
            emitted_body = True
        paragraph.clear()

    for line in lines:
        if _is_furniture(line, furniture):
            flush_paragraph()
            zone = _zone(line)
            element_type = ElementType.HEADER if zone == "header" else ElementType.FOOTER
            elements.append(_element(element_type, line.text.strip(), [line], len(elements)))
            continue
        level = _heading_level(line, body_size, size_levels)
        if level:
            flush_paragraph()
            element_type = (
                ElementType.TITLE if level == 1 and not emitted_body else ElementType.HEADING
            )
            element = _element(element_type, line.text.strip(), [line], len(elements))
            element.heading_level = level
            elements.append(element)
            emitted_body = True
            continue
        if paragraph:
            previous = paragraph[-1]
            gap = previous.y - line.y
            limit = max(previous.font_size, line.font_size, 1) * _PARAGRAPH_GAP_RATIO
            if line.page_number != previous.page_number or gap > limit:
                flush_paragraph()
        paragraph.append(line)
    flush_paragraph()
    return elements


def _element(
    element_type: ElementType,
    text: str,
    lines: list[PdfTextLine],
    index: int,
) -> ParsedElement:
    pages = tuple(dict.fromkeys(line.page_number for line in lines))
    first = lines[0]
    return ParsedElement(
        element_id=f"p{first.page_number}-e{index + 1}",
        element_type=element_type,
        text=text,
        page_number=pages[0],
        reading_order=index,
        provenance=tuple(SourceProvenance(page_number=page) for page in pages),
        metadata={"pdf_layout": "pypdf_visitor_text"},
    )


def _previous_body_index(elements: list[ParsedElement]) -> int | None:
    for index in range(len(elements) - 1, -1, -1):
        if elements[index].element_type not in {ElementType.HEADER, ElementType.FOOTER}:
            return index
    return None


def _merge_cross_page_paragraphs(elements: list[ParsedElement]) -> list[ParsedElement]:
    merged: list[ParsedElement] = []
    seen_body_pages: set[int] = set()
    for element in elements:
        if element.element_type in {ElementType.HEADER, ElementType.FOOTER}:
            merged.append(element)
            continue
        page = element.page_number
        first_on_page = page not in seen_body_pages
        if page is not None:
            seen_body_pages.add(page)
        previous_index = _previous_body_index(merged)
        previous = merged[previous_index] if previous_index is not None else None
        if (
            first_on_page
            and previous is not None
            and previous_index is not None
            and previous.element_type == ElementType.PARAGRAPH
            and element.element_type == ElementType.PARAGRAPH
            and previous.page_number is not None
            and page == previous.page_number + 1
            and not _SENTENCE_END.search(previous.text.strip())
        ):
            merged[previous_index] = _merge_paragraph(previous, element)
            continue
        merged.append(element)
    return merged


def _merge_paragraph(previous: ParsedElement, current: ParsedElement) -> ParsedElement:
    pages = tuple(
        dict.fromkeys(
            [
                *[item.page_number for item in previous.provenance if item.page_number],
                *[item.page_number for item in current.provenance if item.page_number],
            ]
        )
    )
    return ParsedElement(
        element_id=previous.element_id,
        element_type=ElementType.PARAGRAPH,
        text=_join_lines([previous.text, current.text]),
        page_number=previous.page_number,
        heading_level=previous.heading_level,
        section_path=previous.section_path,
        metadata={**previous.metadata, "merged_from": current.element_id},
        raw_text=_join_lines(
            [previous.raw_text or previous.text, current.raw_text or current.text]
        ),
        search_text=_join_lines([previous.text, current.text]),
        reading_order=previous.reading_order,
        provenance=tuple(SourceProvenance(page_number=page) for page in pages),
        confidence=previous.confidence,
    )
