"""Local parsers that preserve structure and report their extraction limits."""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, BinaryIO, TypeAlias
from zipfile import BadZipFile, ZipFile

from docx import Document as WordDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

from .models import (
    AssetReference,
    CoordinateOrigin,
    ElementType,
    ParsedDocument,
    ParsedElement,
    SourceProvenance,
    StructuredTable,
    TableCell,
)
from .omml import formula_texts
from .pdf_layout import elements_from_runs, extract_text_runs

DocumentSource: TypeAlias = bytes | bytearray | str | Path | BinaryIO
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown"}
_MAX_PDF_PAGES = 1000
_MAX_DOCX_EXPANDED_BYTES = 64 * 1024 * 1024
_DOCX_FORMULA_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_SUPERSCRIPT = str.maketrans(
    {
        "0": "⁰",
        "1": "¹",
        "2": "²",
        "3": "³",
        "4": "⁴",
        "5": "⁵",
        "6": "⁶",
        "7": "⁷",
        "8": "⁸",
        "9": "⁹",
        "+": "⁺",
        "-": "⁻",
        "=": "⁼",
        "(": "⁽",
        ")": "⁾",
        "n": "ⁿ",
    }
)
_SUBSCRIPT = str.maketrans(
    {
        "0": "₀",
        "1": "₁",
        "2": "₂",
        "3": "₃",
        "4": "₄",
        "5": "₅",
        "6": "₆",
        "7": "₇",
        "8": "₈",
        "9": "₉",
        "+": "₊",
        "-": "₋",
        "=": "₌",
        "(": "₍",
        ")": "₎",
        "a": "ₐ",
        "e": "ₑ",
        "h": "ₕ",
        "k": "ₖ",
        "l": "ₗ",
        "m": "ₘ",
        "n": "ₙ",
        "o": "ₒ",
        "p": "ₚ",
        "s": "ₛ",
        "t": "ₜ",
        "x": "ₓ",
    }
)


def _source_bytes(source: DocumentSource) -> bytes:
    """Read a binary upload once for hashing and the selected parser."""

    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes()
    read = getattr(source, "read", None)
    if not callable(read):
        raise TypeError("source must be bytes, a path, or a readable binary stream")
    value = read()
    return value.encode("utf-8") if isinstance(value, str) else bytes(value)


def _source_name(source: DocumentSource, file_name: str | None) -> str:
    if file_name:
        return Path(file_name).name
    if isinstance(source, (str, Path)):
        return Path(source).name
    raise ValueError("file_name is required when parsing bytes or a stream")


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("gb18030")


def _package_version(package: str, fallback: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return fallback


class DocumentParser(ABC):
    """Common parser contract; implementations must not call external services."""

    name = "abstract"
    version = "unknown"

    @abstractmethod
    def parse(
        self,
        source: DocumentSource,
        *,
        document_id: str,
        file_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ParsedDocument:
        raise NotImplementedError


class NativeDocumentParser(DocumentParser):
    """Pypdf/python-docx/text parser with explicit gaps for image-only content."""

    name = "native"
    version = "native-structured-v3"

    def parse(
        self,
        source: DocumentSource,
        *,
        document_id: str,
        file_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ParsedDocument:
        name = _source_name(source, file_name)
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise ValueError(f"unsupported document suffix: {suffix}")
        data = _source_bytes(source)
        parse_metadata = dict(metadata or {})
        parse_metadata["source_sha256"] = hashlib.sha256(data).hexdigest()
        if suffix == ".pdf":
            elements, coverage = self._parse_pdf(data, document_id)
            parse_metadata["pdf_coverage"] = coverage
            parse_metadata["page_mapping"] = {
                "status": "available",
                "method": "pypdf_visitor_text",
            }
        elif suffix == ".docx":
            elements, page_mapping = self._parse_docx(data, document_id)
            parse_metadata["page_mapping"] = page_mapping
        elif suffix in {".md", ".markdown"}:
            elements = self._markdown_elements(_decode_text(data))
        else:
            elements = self._text_elements(_decode_text(data))
        return ParsedDocument(
            document_id=document_id,
            file_name=name,
            elements=elements,
            parser=self.name,
            source_type=suffix.lstrip("."),
            metadata=parse_metadata,
            parser_version=self.version,
            parser_config={
                "pdf_ocr": "not_available_in_native_parser",
                "table_structure": "native_docx_xml_only",
                "formula_recognition": "omml_latex",
                "max_pdf_pages": _MAX_PDF_PAGES,
                "max_docx_expanded_bytes": _MAX_DOCX_EXPANDED_BYTES,
            },
        )

    @staticmethod
    def _parse_pdf(data: bytes, document_id: str) -> tuple[list[ParsedElement], dict[str, Any]]:
        reader = PdfReader(BytesIO(data), strict=False)
        page_count = len(reader.pages)
        if page_count > _MAX_PDF_PAGES:
            raise ValueError(f"PDF has {page_count} pages; limit is {_MAX_PDF_PAGES}")
        elements: list[ParsedElement] = []
        text_pages: list[int] = []
        missing_pages: list[int] = []
        runs = []
        for page_number, page in enumerate(reader.pages, start=1):
            page_runs = extract_text_runs(page, page_number)
            if page_runs:
                text_pages.append(page_number)
                runs.extend(page_runs)
                continue
            missing_pages.append(page_number)
            elements.append(
                ParsedElement(
                    element_id=f"p{page_number}-image-only",
                    element_type=ElementType.PAGE_PLACEHOLDER,
                    text="",
                    page_number=page_number,
                    reading_order=len(elements),
                    provenance=(SourceProvenance(page_number=page_number),),
                    asset_refs=(
                        AssetReference(
                            asset_id=f"{document_id}:page:{page_number}",
                            media_type="application/pdf-page",
                            source_kind="source_page",
                            source_locator=f"page:{page_number}",
                            requires_extraction=True,
                            metadata={"content_status": "no_text_layer_or_empty_page"},
                        ),
                    ),
                    metadata={"ocr_status": "not_run", "scan_or_blank_page": True},
                )
            )
        elements.extend(elements_from_runs(runs))
        elements.sort(key=lambda element: (element.page_number or 0, element.reading_order or 0))
        denominator = max(1, page_count)
        coverage = {
            "page_count": page_count,
            "text_page_numbers": text_pages,
            "missing_text_page_numbers": missing_pages,
            "text_coverage": len(text_pages) / denominator,
            "ocr_applied": False,
            "per_page": [
                {"page_number": page, "has_text_layer": page in text_pages}
                for page in range(1, page_count + 1)
            ],
        }
        return elements, coverage


    @classmethod
    def _parse_docx(
        cls, data: bytes, document_id: str
    ) -> tuple[list[ParsedElement], dict[str, Any]]:
        try:
            with ZipFile(BytesIO(data)) as archive:
                expanded_size = sum(item.file_size for item in archive.infolist())
                if expanded_size > _MAX_DOCX_EXPANDED_BYTES:
                    raise ValueError(
                        "DOCX expanded package exceeds "
                        f"{_MAX_DOCX_EXPANDED_BYTES} bytes"
                    )
        except BadZipFile as exc:
            raise ValueError("invalid DOCX package") from exc

        document = WordDocument(BytesIO(data))
        elements: list[ParsedElement] = []
        iter_inner_content = getattr(document, "iter_inner_content", None)
        blocks = (
            iter_inner_content()
            if callable(iter_inner_content)
            else [*document.paragraphs, *document.tables]
        )
        for block in blocks:
            if isinstance(block, Paragraph):
                cls._append_docx_paragraph(elements, block)
                cls._append_docx_images(elements, block, document, document_id)
            elif isinstance(block, Table):
                cls._append_docx_table(elements, block)

        for section_index, section in enumerate(document.sections):
            for part_name, part in (("header", section.header), ("footer", section.footer)):
                for paragraph_index, paragraph in enumerate(part.paragraphs):
                    if text := paragraph.text.strip():
                        elements.append(
                            ParsedElement(
                                element_id=f"{part_name}-{section_index}-{paragraph_index}",
                                element_type=ElementType.HEADER if part_name == "header" else ElementType.FOOTER,
                                text=text,
                                reading_order=len(elements),
                                metadata={
                                    "section_index": section_index,
                                    "linked_to_previous": part.is_linked_to_previous,
                                    "page_number": "unknown_without_render_mapping",
                                },
                            )
                        )
        return elements, {
            "status": "unavailable",
            "method": None,
            "reason": "DOCX paragraphs do not carry rendered page numbers; no page render provider is configured.",
        }

    @staticmethod
    def _append_docx_paragraph(elements: list[ParsedElement], block: Paragraph) -> None:
        display_text, search_text = _paragraph_script_text(block)
        style = (block.style.name if block.style else "").casefold()
        heading_match = re.search(r"heading\s*(\d+)|标题\s*(\d+)", style)
        level = (
            int(next(value for value in heading_match.groups() if value))
            if heading_match
            else None
        )
        if level is not None:
            element_type = ElementType.TITLE if level == 1 and not elements else ElementType.HEADING
        elif "list" in style or "列表" in style:
            element_type = ElementType.LIST_ITEM
        else:
            element_type = ElementType.PARAGRAPH
        if display_text or search_text:
            elements.append(
                ParsedElement(
                    element_id=f"e{len(elements) + 1}",
                    element_type=element_type,
                    text=display_text or search_text,
                    heading_level=level,
                    reading_order=len(elements),
                    raw_text=search_text or display_text,
                    search_text=search_text or display_text,
                    metadata={"docx_style": block.style.name if block.style else None},
                )
            )
        for formula_index, formula in enumerate(
            block._p.findall(f".//{{{_DOCX_FORMULA_NS}}}oMath")
        ):
            formula_xml = ET.tostring(formula, encoding="unicode")
            latex, search, fallback = formula_texts(formula)
            if fallback and "\\" not in latex:
                projection = "concatenated_math_text_runs"
            elif fallback:
                projection = "omml_latex_with_fallback"
            else:
                projection = "omml_latex"
            elements.append(
                ParsedElement(
                    element_id=f"formula-{len(elements) + 1}-{formula_index}",
                    element_type=ElementType.FORMULA,
                    text=latex,
                    reading_order=len(elements),
                    raw_text="".join(formula.itertext()).strip(),
                    search_text=search,
                    metadata={
                        "expression_format": "omml_source_xml",
                        "expression_projection": projection,
                        "latex_fallback": fallback,
                        "source_expression_xml": formula_xml,
                    },
                )
            )

    @staticmethod
    def _append_docx_images(
        elements: list[ParsedElement], block: Paragraph, document: Any, document_id: str
    ) -> None:
        for image_index, blip in enumerate(block._p.findall(".//a:blip", namespaces={"a": "http://schemas.openxmlformats.org/drawingml/2006/main"})):
            relationship_id = blip.get(qn("r:embed"))
            part = document.part.related_parts.get(relationship_id) if relationship_id else None
            drawing_props = block._p.find(".//wp:docPr", namespaces={"wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"})
            locator = str(getattr(part, "partname", "")) or relationship_id or f"inline-image-{image_index}"
            alt_text = ""
            if drawing_props is not None:
                alt_text = drawing_props.get("descr") or drawing_props.get("title") or ""
            elements.append(
                ParsedElement(
                    element_id=f"image-{len(elements) + 1}-{image_index}",
                    element_type=ElementType.IMAGE,
                    text=alt_text,
                    reading_order=len(elements),
                    asset_refs=(
                        AssetReference(
                            asset_id=f"{document_id}:docx:{locator}",
                            media_type=getattr(part, "content_type", None),
                            source_kind="docx_embedded_part",
                            source_locator=locator,
                            requires_extraction=True,
                            metadata={"relationship_id": relationship_id},
                        ),
                    ),
                    metadata={"alt_text_source": "docx_docPr" if alt_text else "none"},
                )
            )

    @staticmethod
    def _append_docx_table(elements: list[ParsedElement], table: Table) -> None:
        grid_rows: list[list[str]] = []
        cell_records: list[dict[str, Any]] = []
        active_vertical: dict[int, dict[str, Any]] = {}
        header_rows = 0
        max_columns = len(table.columns)
        for row_index, row in enumerate(table.rows):
            row_xml = row._tr
            tr_pr = row_xml.find(qn("w:trPr"))
            repeated_header = tr_pr is not None and tr_pr.find(qn("w:tblHeader")) is not None
            if repeated_header:
                header_rows = row_index + 1
            output_row: list[str] = []
            column = 0
            seen_cells: set[int] = set()
            for cell in row.cells:
                tc = cell._tc
                # python-docx 会按网格列重复返回同一个合并单元格，这里只展开一次。
                identity = id(tc)
                if identity in seen_cells:
                    continue
                seen_cells.add(identity)
                tc_pr = tc.tcPr
                span_node = tc_pr.gridSpan if tc_pr is not None else None
                column_span = int(span_node.val) if span_node is not None and span_node.val else 1
                vmerge = tc_pr.vMerge if tc_pr is not None else None
                merge_value = vmerge.val if vmerge is not None else None
                continuation = vmerge is not None and merge_value != "restart"
                cell_text = cell.text.strip()
                if continuation:
                    origin = active_vertical.get(column)
                    if origin is not None:
                        origin["row_span"] += 1
                        cell_text = origin["text"]
                else:
                    record = {
                        "row": row_index,
                        "column": column,
                        "text": cell_text,
                        "row_span": 1,
                        "column_span": column_span,
                        "is_header": repeated_header,
                        "continuation": False,
                    }
                    cell_records.append(record)
                    if vmerge is not None:
                        for col_offset in range(column_span):
                            active_vertical[column + col_offset] = record
                if vmerge is None:
                    for col_offset in range(column_span):
                        active_vertical.pop(column + col_offset, None)
                output_row.append(cell_text)
                output_row.extend([cell_text] * (column_span - 1))
                column += column_span
            max_columns = max(max_columns, len(output_row))
            grid_rows.append(output_row)
        for row in grid_rows:
            row.extend([""] * (max_columns - len(row)))
        text = "\n".join(" | ".join(row) for row in grid_rows)
        if not text.strip(" |\n"):
            return
        structured = StructuredTable(
            rows=grid_rows,
            cells=[TableCell(**record) for record in cell_records],
            header_rows=header_rows,
            structure_source="docx_table_xml",
            metadata={"header_rows_source": "w:tblHeader" if header_rows else "not_marked"},
        )
        elements.append(
            ParsedElement(
                element_id=f"e{len(elements) + 1}",
                element_type=ElementType.TABLE,
                text=text,
                reading_order=len(elements),
                structured_table=structured,
            )
        )

    @staticmethod
    def _markdown_elements(text: str) -> list[ParsedElement]:
        elements: list[ParsedElement] = []
        blocks = re.split(r"\n\s*\n", text)
        for block in blocks:
            value = block.strip()
            if not value:
                continue
            heading = re.fullmatch(r"(#{1,6})\s+(.+)", value)
            if heading:
                level = len(heading.group(1))
                elements.append(
                    ParsedElement(
                        element_id=f"e{len(elements) + 1}",
                        element_type=ElementType.TITLE if level == 1 and not elements else ElementType.HEADING,
                        text=heading.group(2).strip(),
                        heading_level=level,
                        reading_order=len(elements),
                    )
                )
                continue
            lines = value.splitlines()
            if all(re.match(r"^\s*[-*+]\s+", line) for line in lines):
                for line in lines:
                    elements.append(
                        ParsedElement(
                            element_id=f"e{len(elements) + 1}",
                            element_type=ElementType.LIST_ITEM,
                            text=re.sub(r"^\s*[-*+]\s+", "", line).strip(),
                            reading_order=len(elements),
                        )
                    )
            else:
                is_table = len(lines) >= 2 and all("|" in line for line in lines[:2])
                elements.append(
                    ParsedElement(
                        element_id=f"e{len(elements) + 1}",
                        element_type=ElementType.TABLE if is_table else ElementType.PARAGRAPH,
                        text=value,
                        reading_order=len(elements),
                    )
                )
        return elements

    @staticmethod
    def _text_elements(text: str) -> list[ParsedElement]:
        return [
            ParsedElement(
                element_id=f"e{index}",
                element_type=ElementType.PARAGRAPH,
                text=block.strip(),
                reading_order=index - 1,
            )
            for index, block in enumerate(re.split(r"\n\s*\n", text), start=1)
            if block.strip()
        ]


class DoclingParser(DocumentParser):
    """Optional in-process parser; importing it does not load Docling or Torch."""

    name = "docling"

    def __init__(
        self,
        *,
        ocr_enabled: bool = True,
        table_structure_enabled: bool = True,
        formula_enrichment_enabled: bool = False,
        ocr_languages: tuple[str, ...] = ("chi_sim", "eng"),
        document_timeout_seconds: float = 120.0,
    ) -> None:
        self.ocr_enabled = ocr_enabled
        self.table_structure_enabled = table_structure_enabled
        self.formula_enrichment_enabled = formula_enrichment_enabled
        self.ocr_languages = ocr_languages
        self.document_timeout_seconds = document_timeout_seconds

    @property
    def config(self) -> dict[str, Any]:
        return {
            "execution": "in_process_local_pipeline",
            "external_services": False,
            "ocr_enabled": self.ocr_enabled,
            "ocr_languages": list(self.ocr_languages),
            "table_structure_enabled": self.table_structure_enabled,
            "formula_enrichment_enabled": self.formula_enrichment_enabled,
            "document_timeout_seconds": self.document_timeout_seconds,
        }

    def parse(
        self,
        source: DocumentSource,
        *,
        document_id: str,
        file_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ParsedDocument:
        # Optional heavyweight dependencies remain lazy until an explicit parse.
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        name = _source_name(source, file_name)
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise ValueError(f"unsupported document suffix: {suffix}")
        data = _source_bytes(source)
        digest = hashlib.sha256(data).hexdigest()
        temporary_path: Path | None = None
        if isinstance(source, (str, Path)):
            source_path = Path(source)
        else:
            with NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
                temporary.write(data)
                temporary_path = Path(temporary.name)
                source_path = temporary_path
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = self.ocr_enabled
        pipeline_options.do_table_structure = self.table_structure_enabled
        pipeline_options.do_formula_enrichment = self.formula_enrichment_enabled
        if hasattr(pipeline_options, "document_timeout"):
            pipeline_options.document_timeout = self.document_timeout_seconds
        ocr_options = getattr(pipeline_options, "ocr_options", None)
        if ocr_options is not None and hasattr(ocr_options, "lang"):
            ocr_options.lang = list(self.ocr_languages)
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )
        try:
            converted = converter.convert(source_path)
            elements = list(self._elements(converted.document, document_id=document_id))
            docling_version = _package_version("docling", "unknown")
            confidence = _confidence_summary(getattr(converted, "confidence", None))
            parsed_metadata = dict(metadata or {})
            parsed_metadata["source_sha256"] = digest
            parsed_metadata["parser_confidence_report"] = confidence
            parsed_metadata["page_mapping"] = {"status": "available", "method": "docling_provenance"}
            if suffix == ".pdf":
                pages = getattr(converted.document, "pages", {})
                total = len(pages) if hasattr(pages, "__len__") else None
                pages_with_text = sorted(
                    {source.page_number for element in elements for source in element.provenance if source.page_number}
                )
                missing = [page for page in range(1, total + 1) if page not in pages_with_text] if isinstance(total, int) else []
                parsed_metadata["pdf_coverage"] = {
                    "page_count": total,
                    "text_page_numbers": pages_with_text,
                    "missing_text_page_numbers": missing,
                    "text_coverage": len(pages_with_text) / max(1, total) if isinstance(total, int) else None,
                    "ocr_applied": self.ocr_enabled,
                }
            return ParsedDocument(
                document_id=document_id,
                file_name=name,
                elements=elements,
                parser=self.name,
                source_type=suffix.lstrip("."),
                metadata=parsed_metadata,
                parser_version=docling_version,
                parser_config=self.config,
            )
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _elements(document: Any, *, document_id: str = "document") -> Iterable[ParsedElement]:
        page_items = getattr(document, "pages", {}) or {}
        for index, pair in enumerate(document.iterate_items(), start=1):
            item, level = pair if isinstance(pair, tuple) else (pair, None)
            label = str(getattr(item, "label", "")).casefold()
            class_name = type(item).__name__.casefold()
            text = str(getattr(item, "text", "") or "").strip()
            table = _docling_table(item) if "table" in label or "table" in class_name else None
            if table is not None and not text:
                export = getattr(item, "export_to_markdown", None)
                if callable(export):
                    text = str(export(document)).strip()
            provenance = _docling_provenance(item, page_items)
            heading_level = level if isinstance(level, int) else None
            if "title" in label:
                element_type = ElementType.TITLE
            elif "section" in label or "heading" in label:
                element_type = ElementType.HEADING
            elif "list" in label:
                element_type = ElementType.LIST_ITEM
            elif "table" in label or "table" in class_name:
                element_type = ElementType.TABLE
            elif "caption" in label:
                element_type = ElementType.CAPTION
            elif "formula" in label or "formula" in class_name:
                element_type = ElementType.FORMULA
            elif "picture" in label or "image" in class_name:
                element_type = ElementType.IMAGE
            else:
                element_type = ElementType.PARAGRAPH
            image = getattr(item, "image", None)
            uri = getattr(image, "uri", None) if image is not None else None
            assets: tuple[AssetReference, ...] = ()
            if element_type == ElementType.IMAGE or uri:
                assets = (
                    AssetReference(
                        asset_id=f"{document_id}:docling:item:{index}",
                        media_type="image/unknown",
                        source_kind="docling_item",
                        source_locator=f"item:{index}",
                        requires_extraction=True,
                        metadata={"image_uri_present": bool(uri)},
                    ),
                )
            if not text and element_type not in {ElementType.IMAGE, ElementType.PAGE_PLACEHOLDER}:
                continue
            yield ParsedElement(
                element_id=f"e{index}",
                element_type=element_type,
                text=text,
                page_number=next((loc.page_number for loc in provenance if loc.page_number), None),
                heading_level=heading_level,
                reading_order=index - 1,
                provenance=provenance,
                confidence=None,
                structured_table=table,
                asset_refs=assets,
                metadata={
                    "parser_label": label,
                    "source_item_type": type(item).__name__,
                    "formula_expression_format": "docling_text" if element_type == ElementType.FORMULA else None,
                },
            )


def _confidence_summary(confidence: Any) -> dict[str, Any] | None:
    """Persist parser-level grade fields without propagating them to each block."""

    if confidence is None:
        return None
    summary: dict[str, Any] = {"source_type": type(confidence).__name__}
    for name in ("mean_grade", "low_grade", "mean_score", "low_score", "page_confidence"):
        value = getattr(confidence, name, None)
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            summary[name] = value
        else:
            summary[name] = str(value)
    return summary


def _docling_provenance(item: Any, pages: Any) -> tuple[SourceProvenance, ...]:
    result: list[SourceProvenance] = []
    for source in getattr(item, "prov", None) or []:
        page_number = getattr(source, "page_no", None)
        bbox_obj = getattr(source, "bbox", None)
        bbox = None
        origin = CoordinateOrigin.UNKNOWN
        if bbox_obj is not None:
            try:
                bbox = (
                    float(bbox_obj.l),
                    float(bbox_obj.t),
                    float(bbox_obj.r),
                    float(bbox_obj.b),
                )
            except (TypeError, ValueError, AttributeError):
                bbox = None
            raw_origin = str(getattr(bbox_obj, "coord_origin", "")).casefold()
            if "top" in raw_origin:
                origin = CoordinateOrigin.TOP_LEFT
            elif "bottom" in raw_origin:
                origin = CoordinateOrigin.BOTTOM_LEFT
        page = pages.get(page_number) if hasattr(pages, "get") and page_number is not None else None
        size = getattr(page, "size", None)
        result.append(
            SourceProvenance(
                page_number=page_number,
                bbox=bbox,
                page_width=_optional_float(getattr(size, "width", None)),
                page_height=_optional_float(getattr(size, "height", None)),
                coordinate_origin=origin,
            )
        )
    return tuple(result)


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _docling_table(item: Any) -> StructuredTable | None:
    data = getattr(item, "data", None)
    table_data = getattr(data, "table_cells", None) or getattr(item, "table_cells", None)
    if not table_data:
        return None
    row_count = _optional_int(getattr(data, "num_rows", None)) or _optional_int(getattr(item, "num_rows", None))
    col_count = _optional_int(getattr(data, "num_cols", None)) or _optional_int(getattr(item, "num_cols", None))
    max_row = max((_optional_int(getattr(cell, "end_row_offset_idx", None)) or 1 for cell in table_data), default=1)
    max_col = max((_optional_int(getattr(cell, "end_col_offset_idx", None)) or 1 for cell in table_data), default=1)
    row_count = max(row_count or max_row, 1)
    col_count = max(col_count or max_col, 1)
    rows = [["" for _ in range(col_count)] for _ in range(row_count)]
    cells: list[TableCell] = []
    header_rows = 0
    for cell in table_data:
        row = _optional_int(getattr(cell, "start_row_offset_idx", None)) or 0
        column = _optional_int(getattr(cell, "start_col_offset_idx", None)) or 0
        end_row = _optional_int(getattr(cell, "end_row_offset_idx", None)) or row + 1
        end_col = _optional_int(getattr(cell, "end_col_offset_idx", None)) or column + 1
        row = min(max(row, 0), row_count - 1)
        column = min(max(column, 0), col_count - 1)
        row_span, col_span = max(end_row - row, 1), max(end_col - column, 1)
        text = str(getattr(cell, "text", "") or "").strip()
        header = bool(getattr(cell, "column_header", False) or getattr(cell, "row_header", False))
        if getattr(cell, "column_header", False):
            header_rows = max(header_rows, row + row_span)
        cells.append(TableCell(row, column, text, row_span, col_span, header))
        rows[row][column] = text
    return StructuredTable(
        rows=rows,
        cells=cells,
        header_rows=header_rows,
        structure_source="docling_table_cells",
    )


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def default_parser_for(source: DocumentSource, file_name: str | None = None) -> DocumentParser:
    """Use the native parser unless RAG_PARSER explicitly selects Docling.

    Installing Docling on the server must not switch the upload path by itself.
    """

    del source, file_name
    selected = os.environ.get("RAG_PARSER", "native").strip().casefold()
    if selected == "docling":
        return DoclingParser()
    return NativeDocumentParser()


def _paragraph_script_text(paragraph: Paragraph) -> tuple[str, str]:
    """展示文本保留 Unicode 上下标，检索文本保留普通字符。"""

    display_parts: list[str] = []
    search_parts: list[str] = []
    for run in _paragraph_runs(paragraph):
        display, plain = _format_run(run)
        display_parts.append(display)
        search_parts.append(plain)
    return "".join(display_parts).strip(), "".join(search_parts).strip()


def _paragraph_runs(paragraph: Paragraph) -> list[ET.Element]:
    runs: list[ET.Element] = []
    for child in list(paragraph._p):
        local = child.tag.rsplit("}", 1)[-1]
        if local == "r":
            runs.append(child)
        elif local in {"hyperlink", "ins", "smartTag"}:
            runs.extend(child.iter(f"{{{_W_NS}}}r"))
    return runs


def _format_run(run: ET.Element) -> tuple[str, str]:
    parts: list[str] = []
    for node in run.iter():
        local = node.tag.rsplit("}", 1)[-1] if isinstance(node.tag, str) else ""
        if local == "t" and node.text:
            parts.append(node.text)
        elif local == "tab":
            parts.append(" ")
        elif local in {"br", "cr"}:
            parts.append("\n")
    plain = "".join(parts)
    align = _vertical_align(run)
    if align == "superscript":
        return plain.translate(_SUPERSCRIPT), plain
    if align == "subscript":
        return plain.translate(_SUBSCRIPT), plain
    return plain, plain


def _vertical_align(run: ET.Element) -> str | None:
    properties = run.find(f"{{{_W_NS}}}rPr")
    if properties is None:
        return None
    align = properties.find(f"{{{_W_NS}}}vertAlign")
    if align is None:
        return None
    for key, value in align.attrib.items():
        if key.rsplit("}", 1)[-1] == "val":
            return value
    return None
