"""Decide which patient-record scopes a question needs. No model call and no record fetch."""

import re
from dataclasses import dataclass

from app.services.java_tool_client import CLINICAL_CONTEXT_SCOPES

_DEFINITIONAL = re.compile(
    r"是什么|什么是|有哪些症状|怎么办|吃什么药|什么意思|如何预防|怎么预防|有什么用|怎么治疗"
)
_SELF_ANCHOR = re.compile(r"我的|我这个")
_REPORT = re.compile(r"报告单|检查报告|化验单|检验单|检查单|上传的报告|我的报告|这份报告|那份报告|刚上传")
_MEDICATION = re.compile(
    r"我能吃|我可以吃|我能不能|能不能吃|可以吃吗|能吃.+吗|用药|药物|过敏|怀孕|哺乳|孕期|孕哺"
)
_OWN_PREFIX = r"(?:我的|我这个|我最近的|我现在的|我最近|我现在)"
_JUDGMENT = r"(?:正常吗|高吗|低吗|怎么样|多少)"


@dataclass(frozen=True)
class ClinicalRequest:
    scopes: tuple[str, ...]
    report_selection_required: bool
    medication_gap: bool

    @property
    def needs_personal_records(self) -> bool:
        return bool(self.scopes) or self.report_selection_required


def latest_user_text(state: dict) -> str:
    for message in reversed(state.get("messages") or []):
        if getattr(message, "type", None) in {"human", "user"}:
            content = getattr(message, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


def clinical_request(goal: str | None, latest: str) -> ClinicalRequest:
    texts = [
        text.strip()
        for text in (goal or "", latest)
        if isinstance(text, str) and text.strip()
    ]
    scopes: list[str] = []
    report = False
    medication = False
    for text in texts:
        report = report or _report_requested(text)
        medication = medication or _medication_question(text)
        for scope in _scopes_for_text(text):
            if scope not in scopes:
                scopes.append(scope)
    if report and "document_catalog" not in scopes:
        scopes.append("document_catalog")
    unknown = [scope for scope in scopes if scope not in CLINICAL_CONTEXT_SCOPES]
    if unknown:
        raise RuntimeError(f"clinical scope is not allowed: {','.join(unknown)}")
    return ClinicalRequest(tuple(scopes), report, medication)


def _report_requested(text: str) -> bool:
    if not _REPORT.search(text):
        return False
    if _DEFINITIONAL.search(text) and not re.search(r"我的报告|这份报告|那份报告|帮我看|看看|上传", text):
        return False
    return re.search(r"我|帮我|看看|上传|这份|那份", text) is not None


def _medication_question(text: str) -> bool:
    if not _MEDICATION.search(text):
        return False
    if "我" not in text and "过敏" not in text:
        return False
    if _DEFINITIONAL.search(text) and not _SELF_ANCHOR.search(text) and "能吃" not in text and "过敏" not in text:
        return False
    return True


def _own_metric(text: str, metric: str) -> bool:
    if re.search(rf"{_OWN_PREFIX}.{{0,12}}{metric}", text):
        return True
    if re.search(rf"我{metric}", text):
        return True
    if "我" not in text or not re.search(rf"{metric}.{{0,6}}{_JUDGMENT}", text):
        return False
    return not (_DEFINITIONAL.search(text) and not _SELF_ANCHOR.search(text))


def _scopes_for_text(text: str) -> list[str]:
    if _DEFINITIONAL.search(text) and not _SELF_ANCHOR.search(text) and not _medication_question(text):
        if not _report_requested(text):
            return []

    scopes: list[str] = []

    def add(*names: str) -> None:
        for name in names:
            if name not in scopes:
                scopes.append(name)

    if _own_metric(text, "血压") or _own_metric(text, "高压") or _own_metric(text, "低压"):
        add("demographics", "blood_pressure", "past_history")
    if _own_metric(text, "血糖"):
        add("demographics", "blood_glucose", "past_history")
    if _own_metric(text, "心率") or _own_metric(text, "脉搏"):
        add("demographics", "heart_rate")
    if _own_metric(text, "血氧"):
        add("demographics", "spo2")
    if _own_metric(text, "体温") or re.search(r"我发烧|我的体温|我体温", text):
        add("demographics", "temperature")
    if _own_metric(text, "呼吸"):
        add("demographics", "respiratory_rate")
    if (
        _own_metric(text, "体重")
        or _own_metric(text, "身高")
        or _own_metric(text, "腰围")
        or re.search(r"我的\s*bmi|我胖不胖|我是不是肥胖|腹型肥胖", text, re.IGNORECASE)
    ):
        add("demographics", "anthropometrics")
    if _medication_question(text) or re.search(r"我.{0,8}过敏|我的过敏|过敏史", text):
        add("demographics", "allergies", "past_history")
    if re.search(r"家族史|我的家族|家里人有|家里有|我家有|父母有|遗传风险|筛查", text) and "我" in text:
        if not (_DEFINITIONAL.search(text) and not _SELF_ANCHOR.search(text)):
            add("demographics", "family_history")
    if re.search(r"我(?:的)?(?:吸烟|抽烟|喝酒|饮酒|职业)|我平时吸烟|我有吸烟|我吸烟|我抽烟|我喝酒|我饮酒", text):
        add("personal_history")
    if re.search(r"我(?:以前|既往|做过手术|有慢病|的病史|的既往)", text):
        add("demographics", "past_history")
    return scopes
