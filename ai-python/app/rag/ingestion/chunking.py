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
from .models import Chunk, DocumentType, ElementType, ParsedDocument, ParsedElement


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
            sentences = _sentence_units(unit)
            chunks.extend(
                self._pack(sentences, respect_section_boundaries=False)
            )
        return chunks


def _unit(elements: Sequence[ParsedElement], text: str | None = None) -> _Unit:
    """把一组原始元素合成待切块单元，并保留来源位置。"""
    rendered = text if text is not None else "\n".join(element.text for element in elements)
    return _Unit(
        text=rendered.strip(),
        element_ids=tuple(element.element_id for element in elements),
        page_numbers=tuple(
            sorted({element.page_number for element in elements if element.page_number is not None})
        ),
        section_path=next(
            (element.section_path for element in reversed(elements) if element.section_path), ()
        ),
    )


def _element_units(document: ParsedDocument) -> list[_Unit]:
    """把每个文档元素分别作为一个待切块单元。"""
    return [_unit([element]) for element in document.elements if element.text.strip()]


def _sentence_units(unit: _Unit) -> list[_Unit]:
    """Split on sentence/line boundaries; token-window only an oversized sentence."""

    parts = [
        part.strip()
        for part in re.split(r"(?<=[。！？!?；;])\s*|\n+", unit.text)
        if part.strip()
    ]
    return [
        _Unit(
            text=part,
            element_ids=unit.element_ids,
            page_numbers=unit.page_numbers,
            section_path=unit.section_path,
        )
        for part in parts
    ]


def _section_units(document: ParsedDocument) -> list[_Unit]:
    """Build leaf sections without emitting a document-title-only chunk."""

    units: list[_Unit] = []
    preamble: list[ParsedElement] = []
    section: list[ParsedElement] = []
    has_section_heading = False
    for element in document.elements:
        if element.element_type == ElementType.TITLE:
            if not has_section_heading and not section:
                preamble.append(element)
            continue
        if element.element_type == ElementType.HEADING:
            if section:
                units.append(_unit(section))
            section = [element]
            has_section_heading = True
            continue
        if has_section_heading:
            section.append(element)
        else:
            preamble.append(element)
    if section:
        units.append(_unit(section))
    if not units and preamble:
        units.append(_unit(preamble))
    elif units and any(
        element.element_type != ElementType.TITLE for element in preamble
    ):
        non_title_preamble = [
            element for element in preamble if element.element_type != ElementType.TITLE
        ]
        units.insert(0, _unit(non_title_preamble))
    return units


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
            if element.element_type in {ElementType.TITLE, ElementType.HEADING}:
                if group:
                    units.append(_unit([*context, *group]))
                    group = []
                context = [element]
                continue
            if self._question.search(element.text) and group:
                units.append(_unit([*context, *group]))
                group = []
            group.append(element)
        if group:
            units.append(_unit([*context, *group]))
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
        units: list[_Unit] = []
        pending: list[ParsedElement] = []
        for element in document.elements:
            if element.element_type == ElementType.TABLE:
                if pending:
                    units.append(_unit(pending))
                    pending = []
                units.append(_unit([element]))
            else:
                pending.append(element)
        if pending:
            units.append(_unit(pending))
        return self._pack(units)


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
