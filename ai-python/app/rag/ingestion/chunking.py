"""按文档结构和模型长度限制，把资料切成适合检索的小段。

“token”是模型读取文字时使用的计量单位；每段不能太长。相邻段保留少量
重叠文字，避免关键信息刚好被切断。问答、流程、目录等文档采用不同切法。
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from .config import IngestionConfig
from .models import (
    Chunk,
    DocumentType,
    ElementType,
    ParsedDocument,
    ParsedElement,
    StructuredTable,
)


class Tokenizer(Protocol):
    """切块器只需要编码和解码能力，不依赖某个固定分词库。"""

    def encode(self, text: str, **kwargs: Any) -> Sequence[Any]: ...

    def decode(self, tokens: Sequence[Any], **kwargs: Any) -> str: ...


class HuggingFaceTokenizer:
    """首次需要计算 token 时才加载分词模型，减少服务启动开销。"""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._tokenizer: Any | None = None

    def _get(self) -> Any:
        if self._tokenizer is None:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        return self._tokenizer

    def encode(self, text: str, **kwargs: Any) -> Sequence[Any]:
        return self._get().encode(text, add_special_tokens=False)

    def decode(self, tokens: Sequence[Any], **kwargs: Any) -> str:
        return self._get().decode(tokens, skip_special_tokens=True)


@dataclass(slots=True)
class _Unit:
    """切块前的临时文本单元，保留原元素、页码和章节位置。"""

    text: str
    element_ids: tuple[str, ...]
    page_numbers: tuple[int, ...]
    section_path: tuple[str, ...]
    kind: str = "prose"
    table: StructuredTable | None = None
    caption: str = ""


@dataclass(slots=True)
class _Piece:
    """按元素类型拆开的临时片段，公式绑定会改写其中的句子列表。"""

    kind: str
    element: ParsedElement
    sentences: list[str]
    prev_text: str | None = None
    prev_element: ParsedElement | None = None
    next_text: str | None = None
    next_element: ParsedElement | None = None


class ChunkingStrategy(ABC):
    """不同文档类型共用的长度控制和相邻片段重叠逻辑。"""

    name = "abstract"

    def __init__(self, tokenizer: Tokenizer, config: IngestionConfig) -> None:
        self.tokenizer = tokenizer
        self.config = config

    @abstractmethod
    def split(self, document: ParsedDocument) -> list[Chunk]:
        raise NotImplementedError

    def _encode(self, text: str) -> list[Any]:
        try:
            return list(self.tokenizer.encode(text, add_special_tokens=False))
        except TypeError:
            return list(self.tokenizer.encode(text))

    def _decode(self, tokens: Sequence[Any]) -> str:
        try:
            return self.tokenizer.decode(tokens, skip_special_tokens=True).strip()
        except TypeError:
            return self.tokenizer.decode(tokens).strip()

    def _window(self, unit: _Unit) -> list[Chunk]:
        """单个单元太长时，按 token 长度滑动切成多段。"""
        tokens = self._encode(unit.text)
        if not tokens:
            return []
        size = self.config.max_tokens
        step = size - self.config.overlap_tokens
        starts = list(range(0, len(tokens), step))
        if len(starts) > 1 and len(tokens) - starts[-1] < self.config.min_chunk_tokens:
            adjusted = max(0, len(tokens) - size)
            if adjusted > starts[-2]:
                starts[-1] = adjusted
            else:
                starts.pop()
        chunks: list[Chunk] = []
        for start in starts:
            text = self._decode(tokens[start : start + size])
            if text:
                chunks.append(
                    Chunk(
                        text=text,
                        element_ids=unit.element_ids,
                        page_numbers=unit.page_numbers,
                        section_path=unit.section_path,
                    )
                )
            if start + size >= len(tokens):
                break
        return chunks

    def _pack(
        self,
        units: list[_Unit],
        *,
        respect_section_boundaries: bool = True,
    ) -> list[Chunk]:
        """尽量把相邻短单元合并，达到长度上限或章节边界就输出一段。"""
        chunks: list[Chunk] = []
        current_text = ""
        current_ids: tuple[str, ...] = ()
        current_pages: tuple[int, ...] = ()
        current_section: tuple[str, ...] = ()

        def emit() -> None:
            nonlocal current_text, current_ids, current_pages, current_section
            if current_text.strip():
                chunks.append(
                    Chunk(
                        text=current_text.strip(),
                        element_ids=current_ids,
                        page_numbers=current_pages,
                        section_path=current_section,
                    )
                )
            current_text = ""
            current_ids = ()
            current_pages = ()
            current_section = ()

        for unit in units:
            if unit.kind == "table":
                emit()
                chunks.extend(self._table_chunks(unit))
                continue
            if unit.kind == "formula":
                emit()
                chunks.extend(self._formula_chunks(unit))
                continue
            if (
                respect_section_boundaries
                and current_text
                and unit.section_path != current_section
            ):
                emit()
            if len(self._encode(unit.text)) > self.config.max_tokens:
                emit()
                chunks.extend(self._window(unit))
                continue
            candidate = f"{current_text}\n\n{unit.text}".strip()
            if current_text and len(self._encode(candidate)) > self.config.max_tokens:
                previous_text = current_text
                previous_ids = current_ids
                previous_pages = current_pages
                emit()
                overlap = ""
                if self.config.overlap_tokens:
                    previous_tokens = self._encode(previous_text)
                    overlap = self._decode(previous_tokens[-self.config.overlap_tokens :])
                candidate = f"{overlap}\n\n{unit.text}".strip()
                if len(self._encode(candidate)) > self.config.max_tokens:
                    candidate = unit.text
                    previous_ids = ()
                    previous_pages = ()
                current_ids = tuple(dict.fromkeys((*previous_ids, *unit.element_ids)))
                current_pages = tuple(sorted({*previous_pages, *unit.page_numbers}))
            else:
                current_ids = tuple(dict.fromkeys((*current_ids, *unit.element_ids)))
                current_pages = tuple(sorted({*current_pages, *unit.page_numbers}))
            current_text = candidate
            current_section = unit.section_path or current_section
        emit()
        return chunks

    def _split_units_independently(self, units: list[_Unit]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for unit in units:
            if unit.kind == "table":
                chunks.extend(self._table_chunks(unit))
            elif unit.kind == "formula":
                chunks.extend(self._formula_chunks(unit))
            else:
                chunks.extend(
                    self._pack(
                        _sentence_units(unit),
                        respect_section_boundaries=False,
                    )
                )
        return chunks

    def _formula_chunks(self, unit: _Unit) -> list[Chunk]:
        """公式和前后解释保持在同一片段里，只有超长时才按长度切开。"""

        text = unit.text.strip()
        if not text:
            return []
        metadata = {"content_kind": "formula"}
        if len(self._encode(text)) <= self.config.max_tokens:
            return [
                Chunk(
                    text=text,
                    element_ids=unit.element_ids,
                    page_numbers=unit.page_numbers,
                    section_path=unit.section_path,
                    metadata=metadata,
                )
            ]
        chunks = self._window(unit)
        for chunk in chunks:
            chunk.metadata = {**metadata, **chunk.metadata}
        return chunks

    def _table_chunks(self, unit: _Unit) -> list[Chunk]:
        """表格单独成段；超长时按行切开，并在每段重复表头。"""

        table = unit.table or _pipe_table(unit.text)
        if table is None or not table.rows:
            return self._atomic_chunks(unit, content_kind="table")
        header_count = min(max(table.header_rows, 0), len(table.rows))
        full = _render_table(unit.caption, table.rows[:header_count], table.rows[header_count:])
        if (
            header_count == 0
            and len(table.rows) > 1
            and len(self._encode(full)) > self.config.max_tokens
        ):
            header_count = 1
        header = table.rows[:header_count]
        body = table.rows[header_count:]
        rendered = [
            _render_table(unit.caption, header, body[start:end])
            for start, end in _table_row_windows(
                body,
                lambda rows: len(self._encode(_render_table(unit.caption, header, rows))),
                self.config.max_tokens,
            )
        ]
        if not rendered:
            rendered = [_render_table(unit.caption, header, body)]
        header_lines = [unit.caption] if unit.caption else []
        header_lines.extend(" | ".join(cell.strip() for cell in row) for row in header)
        metadata = {
            "content_kind": "table",
            "table_element_id": unit.element_ids[0] if unit.element_ids else "",
            "table_part_count": len(rendered),
            "table_header_lines": "\n".join(line for line in header_lines if line),
        }
        chunks: list[Chunk] = []
        for index, text in enumerate(rendered):
            if not text:
                continue
            chunks.append(
                Chunk(
                    text=text,
                    element_ids=unit.element_ids,
                    page_numbers=unit.page_numbers,
                    section_path=unit.section_path,
                    metadata={
                        **metadata,
                        "table_part_index": index,
                        "table_part_count": len(rendered),
                    },
                )
            )
        if chunks:
            total = len(chunks)
            for index, chunk in enumerate(chunks):
                chunk.metadata["table_part_index"] = index
                chunk.metadata["table_part_count"] = total
        return chunks

    def _atomic_chunks(self, unit: _Unit, *, content_kind: str) -> list[Chunk]:
        text = unit.text.strip()
        if unit.caption and unit.caption not in text:
            text = f"{unit.caption}\n{text}".strip()
        if not text:
            return []
        metadata = {"content_kind": content_kind}
        if len(self._encode(text)) <= self.config.max_tokens:
            return [
                Chunk(
                    text=text,
                    element_ids=unit.element_ids,
                    page_numbers=unit.page_numbers,
                    section_path=unit.section_path,
                    metadata=metadata,
                )
            ]
        chunks = self._window(_Unit(
            text=text,
            element_ids=unit.element_ids,
            page_numbers=unit.page_numbers,
            section_path=unit.section_path,
            kind=unit.kind,
        ))
        for chunk in chunks:
            chunk.metadata = {**metadata, **chunk.metadata}
        return chunks


_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;])\s*|\n+")
_TABLE_CAPTION = re.compile(r"^表\s*[0-9０-９一二三四五六七八九十]+")
_MARKDOWN_SEPARATOR = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
_FURNITURE = {ElementType.HEADER, ElementType.FOOTER}


def _unit(elements: Sequence[ParsedElement], text: str | None = None) -> _Unit:
    """把一组原始元素合成待切块单元，并保留来源位置。"""
    rendered = text if text is not None else "\n".join(element.text for element in elements)
    return _Unit(
        text=rendered.strip(),
        element_ids=tuple(dict.fromkeys(element.element_id for element in elements)),
        page_numbers=_page_numbers(elements),
        section_path=next(
            (element.section_path for element in reversed(elements) if element.section_path), ()
        ),
    )


def _page_numbers(elements: Sequence[ParsedElement]) -> tuple[int, ...]:
    pages: list[int] = []
    for element in elements:
        if element.provenance:
            pages.extend(
                item.page_number for item in element.provenance if item.page_number is not None
            )
        elif element.page_number is not None:
            pages.append(element.page_number)
    return tuple(sorted(set(pages)))


def _element_units(document: ParsedDocument) -> list[_Unit]:
    """把每个文档元素分别作为一个待切块单元。"""
    units: list[_Unit] = []
    for element in document.elements:
        if element.element_type in _FURNITURE or not element.text.strip():
            continue
        if element.element_type == ElementType.TABLE:
            units.append(_table_unit(element, ""))
        elif element.element_type == ElementType.FORMULA:
            units.append(_formula_only(element))
        else:
            units.append(_unit([element]))
    return units


def _formula_only(element: ParsedElement) -> _Unit:
    unit = _unit([element])
    unit.kind = "formula"
    return unit


def _table_unit(
    element: ParsedElement,
    caption: str,
    extra: Sequence[ParsedElement] = (),
) -> _Unit:
    table_caption = caption
    if not table_caption and element.structured_table and element.structured_table.caption:
        table_caption = element.structured_table.caption
    sources = [element, *extra]
    return _Unit(
        text=element.text.strip(),
        element_ids=tuple(dict.fromkeys(item.element_id for item in sources)),
        page_numbers=_page_numbers(sources),
        section_path=next(
            (item.section_path for item in reversed(sources) if item.section_path), ()
        ),
        kind="table",
        table=element.structured_table,
        caption=table_caption or "",
    )


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]


def _sentence_units(unit: _Unit) -> list[_Unit]:
    """按句子和换行拆开正文。表格、公式不再从这里拆。"""

    if unit.kind in {"table", "formula"}:
        return [unit]
    return [
        _Unit(
            text=part,
            element_ids=unit.element_ids,
            page_numbers=unit.page_numbers,
            section_path=unit.section_path,
            kind=unit.kind,
        )
        for part in _split_sentences(unit.text)
    ]


def _section_units(document: ParsedDocument) -> list[_Unit]:
    """Build leaf sections without emitting a document-title-only chunk."""

    units: list[_Unit] = []
    preamble: list[ParsedElement] = []
    section: list[ParsedElement] = []
    has_section_heading = False
    for element in document.elements:
        if element.element_type in _FURNITURE:
            continue
        if element.element_type == ElementType.TITLE:
            if not has_section_heading and not section:
                preamble.append(element)
            continue
        if element.element_type == ElementType.HEADING:
            if section:
                units.extend(_expand_group(section))
            section = [element]
            has_section_heading = True
            continue
        if has_section_heading:
            section.append(element)
        else:
            preamble.append(element)
    if section:
        units.extend(_expand_group(section))
    if not units and preamble:
        units.extend(_expand_group(preamble))
    elif units and any(element.element_type != ElementType.TITLE for element in preamble):
        non_title_preamble = [
            element for element in preamble if element.element_type != ElementType.TITLE
        ]
        units = [*_expand_group(non_title_preamble), *units]
    return units


def _expand_group(elements: Sequence[ParsedElement]) -> list[_Unit]:
    """正文按句切分；表格独立；公式带上前后各一句解释。"""

    pieces = _pieces(elements)
    for index, piece in enumerate(pieces):
        if piece.kind != "formula":
            continue
        piece.prev_text, piece.prev_element = _take_sentence(pieces, index - 1, -1)
        piece.next_text, piece.next_element = _take_sentence(pieces, index + 1, 1)

    units: list[_Unit] = []
    bucket: list[tuple[ParsedElement, str]] = []
    pending_caption: tuple[str, ParsedElement] | None = None

    def flush_prose() -> None:
        texts: list[str] = []
        ids: list[str] = []
        sources: list[ParsedElement] = []
        section: tuple[str, ...] = ()
        for element, text in bucket:
            cleaned = text.strip()
            if not cleaned:
                continue
            texts.append(cleaned)
            ids.append(element.element_id)
            sources.append(element)
            section = element.section_path or section
        bucket.clear()
        if texts:
            units.append(
                _Unit(
                    text="\n".join(texts),
                    element_ids=tuple(dict.fromkeys(ids)),
                    page_numbers=_page_numbers(sources),
                    section_path=section,
                )
            )

    def consume_pending_caption() -> None:
        nonlocal pending_caption
        if pending_caption is None:
            return
        bucket.append(pending_caption)
        pending_caption = None

    for piece in pieces:
        if piece.kind == "caption":
            flush_prose()
            if pending_caption is not None:
                bucket.append(pending_caption)
                flush_prose()
            pending_caption = (piece.element.text.strip(), piece.element)
            continue
        if piece.kind == "table":
            stolen, stolen_elements = _steal_caption(bucket)
            flush_prose()
            caption = ""
            extra: list[ParsedElement] = []
            if pending_caption is not None:
                caption = pending_caption[0]
                extra.append(pending_caption[1])
                pending_caption = None
            if stolen:
                caption = caption or stolen
                extra.extend(stolen_elements)
            units.append(_table_unit(piece.element, caption, extra))
            continue
        consume_pending_caption()
        if piece.kind == "heading":
            bucket.append((piece.element, piece.element.text.strip()))
            continue
        if piece.kind == "formula":
            heading_text = ""
            heading_elements: list[ParsedElement] = []
            if _bucket_is_heading_only(bucket):
                heading_text = "\n".join(text.strip() for _, text in bucket if text.strip())
                heading_elements = [element for element, text in bucket if text.strip()]
                bucket.clear()
            else:
                flush_prose()
            units.append(_formula_unit(piece, heading_text, heading_elements))
            continue
        bucket.append((piece.element, "\n".join(piece.sentences)))
    flush_prose()
    if pending_caption is not None:
        units.append(_unit([pending_caption[1]], pending_caption[0]))
    return [unit for unit in units if unit.text.strip()]


def _pieces(elements: Sequence[ParsedElement]) -> list[_Piece]:
    pieces: list[_Piece] = []
    for element in elements:
        if element.element_type in _FURNITURE:
            continue
        if element.element_type == ElementType.TABLE:
            pieces.append(_Piece("table", element, []))
        elif element.element_type == ElementType.FORMULA:
            pieces.append(_Piece("formula", element, []))
        elif element.element_type == ElementType.CAPTION:
            pieces.append(_Piece("caption", element, []))
        elif element.element_type in {ElementType.TITLE, ElementType.HEADING}:
            pieces.append(_Piece("heading", element, []))
        elif element.text.strip():
            pieces.append(_Piece("prose", element, _split_sentences(element.text)))
    return pieces


def _take_sentence(
    pieces: Sequence[_Piece],
    start: int,
    step: int,
) -> tuple[str | None, ParsedElement | None]:
    index = start
    while 0 <= index < len(pieces):
        piece = pieces[index]
        if piece.kind in {"heading", "table"}:
            return None, None
        if piece.kind in {"formula", "caption"}:
            index += step
            continue
        if piece.sentences:
            sentence = piece.sentences.pop() if step < 0 else piece.sentences.pop(0)
            return sentence, piece.element
        index += step
    return None, None


def _bucket_is_heading_only(bucket: Sequence[tuple[ParsedElement, str]]) -> bool:
    filled = [(element, text) for element, text in bucket if text.strip()]
    return bool(filled) and all(
        element.element_type in {ElementType.TITLE, ElementType.HEADING}
        for element, _ in filled
    )


def _steal_caption(
    bucket: list[tuple[ParsedElement, str]],
) -> tuple[str, list[ParsedElement]]:
    if not bucket:
        return "", []
    element, text = bucket[-1]
    if element.element_type == ElementType.CAPTION and text.strip():
        bucket.pop()
        return text.strip(), [element]
    sentences = _split_sentences(text)
    if sentences and _TABLE_CAPTION.match(sentences[-1]):
        caption = sentences.pop()
        bucket[-1] = (element, "\n".join(sentences))
        return caption, [element]
    return "", []


def _formula_unit(
    piece: _Piece,
    heading_text: str,
    heading_elements: Sequence[ParsedElement],
) -> _Unit:
    parts = [
        part.strip()
        for part in (
            heading_text,
            piece.prev_text or "",
            piece.element.text,
            piece.next_text or "",
        )
        if part and part.strip()
    ]
    sources = [
        *heading_elements,
        *([piece.prev_element] if piece.prev_element is not None else []),
        piece.element,
        *([piece.next_element] if piece.next_element is not None else []),
    ]
    return _Unit(
        text="\n".join(parts),
        element_ids=tuple(dict.fromkeys(element.element_id for element in sources)),
        page_numbers=_page_numbers(sources),
        section_path=next(
            (element.section_path for element in reversed(sources) if element.section_path),
            (),
        ),
        kind="formula",
    )


def _render_table(caption: str, header: Sequence[Sequence[str]], body: Sequence[Sequence[str]]) -> str:
    lines = [caption] if caption else []
    lines.extend(" | ".join(cell.strip() for cell in row) for row in [*header, *body])
    return "\n".join(line for line in lines if line).strip()


def _table_row_windows(
    rows: Sequence[Sequence[str]],
    length_of: Any,
    max_tokens: int,
) -> list[tuple[int, int]]:
    if not rows:
        return [(0, 0)]
    windows: list[tuple[int, int]] = []
    start = 0
    for index in range(len(rows)):
        if index > start and length_of(rows[start : index + 1]) > max_tokens:
            windows.append((start, index))
            start = index
    windows.append((start, len(rows)))
    return windows


def _pipe_table(text: str) -> StructuredTable | None:
    rows: list[list[str]] = []
    for line in text.splitlines():
        if "|" not in line:
            return None
        if _MARKDOWN_SEPARATOR.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if any(cells):
            rows.append(cells)
    if len(rows) < 2:
        return None
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    return StructuredTable(rows=normalized, header_rows=1, structure_source="markdown_pipe")


class HybridChunkingStrategy(ChunkingStrategy):
    """普通文档默认按章节和长度切块，不调用模型做语义切分。"""

    name = "hybrid"

    def split(self, document: ParsedDocument) -> list[Chunk]:
        return self._split_units_independently(_section_units(document))


class FAQChunkingStrategy(ChunkingStrategy):
    """尽量把一个问题与其答案留在同一检索片段。"""

    name = "faq_pair"
    _question = re.compile(r"^\s*(?:Q|问)\s*[:：]|[？?]\s*$", re.IGNORECASE)

    def split(self, document: ParsedDocument) -> list[Chunk]:
        units: list[_Unit] = []
        group: list[ParsedElement] = []
        context: list[ParsedElement] = []
        for element in document.elements:
            if element.element_type in _FURNITURE:
                continue
            if element.element_type in {ElementType.TITLE, ElementType.HEADING}:
                if group:
                    units.extend(_expand_group([*context, *group]))
                    group = []
                context = [element]
                continue
            if self._question.search(element.text) and group:
                units.extend(_expand_group([*context, *group]))
                group = []
            group.append(element)
        if group:
            units.extend(_expand_group([*context, *group]))
        return self._split_units_independently(units or _element_units(document))


class ProcedureChunkingStrategy(ChunkingStrategy):
    """按流程章节切段，尽量让步骤留在相邻的检索结果中。"""

    name = "procedure_steps"

    def split(self, document: ParsedDocument) -> list[Chunk]:
        return self._split_units_independently(_section_units(document))


class PolicyChunkingStrategy(ProcedureChunkingStrategy):
    """院内制度沿用按章节切段的方式。"""

    name = "policy_sections"


class HospitalGuideChunkingStrategy(ProcedureChunkingStrategy):
    """就诊指南沿用按章节切段的方式。"""

    name = "guide_sections"


class MedicalPaperChunkingStrategy(ProcedureChunkingStrategy):
    """医学论文沿用按章节切段的方式。"""

    name = "paper_sections"


class DirectoryChunkingStrategy(ChunkingStrategy):
    """目录文档优先让表格独立成段，方便查到完整条目。"""

    name = "directory_entries"

    def split(self, document: ParsedDocument) -> list[Chunk]:
        body = [
            element
            for element in document.elements
            if element.element_type not in _FURNITURE
        ]
        return self._pack(_expand_group(body) or _element_units(document))


class ChunkingRouter:
    """根据文档分类结果选择相应的切块策略。"""

    def __init__(self, tokenizer: Tokenizer, config: IngestionConfig) -> None:
        self._strategies: dict[DocumentType, ChunkingStrategy] = {
            DocumentType.FAQ: FAQChunkingStrategy(tokenizer, config),
            DocumentType.PROCEDURE: ProcedureChunkingStrategy(tokenizer, config),
            DocumentType.POLICY: PolicyChunkingStrategy(tokenizer, config),
            DocumentType.DIRECTORY: DirectoryChunkingStrategy(tokenizer, config),
            DocumentType.HOSPITAL_GUIDE: HospitalGuideChunkingStrategy(
                tokenizer, config
            ),
            DocumentType.MEDICAL_PAPER: MedicalPaperChunkingStrategy(
                tokenizer, config
            ),
            DocumentType.GENERAL: HybridChunkingStrategy(tokenizer, config),
        }

    def select_strategy(self, document_type: DocumentType) -> ChunkingStrategy:
        try:
            return self._strategies[document_type]
        except KeyError as exc:
            raise ValueError(f"unsupported document type: {document_type}") from exc
