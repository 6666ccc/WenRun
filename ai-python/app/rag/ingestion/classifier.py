"""Deterministic layout/keyword classification for hospital documents."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from .models import DocumentType, ElementType, ParsedDocument


class DocumentClassifier(ABC):
    @abstractmethod
    def classify(self, document: ParsedDocument) -> DocumentType:
        raise NotImplementedError


class RuleBasedDocumentClassifier(DocumentClassifier):
    """Classify by explicit textual and structural signals, without model calls."""

    _faq = re.compile(r"常见问题|问答|FAQ|(?:^|\n)\s*(?:Q|问)\s*[:：]", re.IGNORECASE)
    _procedure = re.compile(r"办理流程|就诊流程|操作步骤|申请流程|第[一二三四五六七八九十]+步|步骤\s*\d+")
    _policy = re.compile(r"管理制度|管理办法|规章制度|实施细则|适用范围|本规定|条例")
    _directory = re.compile(r"科室介绍|科室目录|专家介绍|医生简介|门诊时间|联系电话|院区地址")
    _guide = re.compile(
        r"门诊指南|就医指南|就诊指南|患者须知|门诊服务|办事指南|"
        r"(?:挂号|退号|预约|缴费|报到|候诊|取药|检查)(?:流程|规则|须知|说明)"
    )
    _paper_section = re.compile(
        r"^(?:摘\s*要|关键词|引言|背景|材料与方法|对象与方法|方法|结果|讨论|结论|参考文献)$"
    )

    def classify(self, document: ParsedDocument) -> DocumentType:
        if not document.elements:
            raise ValueError("cannot classify a document without elements")
        sample = "\n".join(
            [document.file_name, *(element.text for element in document.elements[:80])]
        )
        scores = {
            DocumentType.FAQ: len(self._faq.findall(sample)),
            DocumentType.PROCEDURE: len(self._procedure.findall(sample)),
            DocumentType.POLICY: len(self._policy.findall(sample)),
            DocumentType.DIRECTORY: len(self._directory.findall(sample)),
            DocumentType.HOSPITAL_GUIDE: len(self._guide.findall(sample)),
            DocumentType.MEDICAL_PAPER: 0,
        }
        list_items = sum(
            element.element_type == ElementType.LIST_ITEM for element in document.elements
        )
        tables = sum(
            element.element_type == ElementType.TABLE for element in document.elements
        )
        question_lines = sum(
            bool(
                re.match(
                    r"\s*(?:Q|问)\s*[:：]|.+[？?]\s*$",
                    element.text,
                    re.IGNORECASE,
                )
            )
            for element in document.elements
        )
        if question_lines >= 2:
            scores[DocumentType.FAQ] += 2
        if list_items >= 3:
            scores[DocumentType.PROCEDURE] += 1
        if tables >= 1 and scores[DocumentType.DIRECTORY]:
            scores[DocumentType.DIRECTORY] += 1
        paper_sections = sum(
            element.element_type in {ElementType.TITLE, ElementType.HEADING}
            and bool(self._paper_section.fullmatch(element.text.strip()))
            for element in document.elements
        )
        if paper_sections >= 2:
            scores[DocumentType.MEDICAL_PAPER] = paper_sections + 1
        winner, score = max(scores.items(), key=lambda item: item[1])
        return winner if score > 0 else DocumentType.GENERAL
