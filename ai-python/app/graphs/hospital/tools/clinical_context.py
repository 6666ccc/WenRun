"""知识助手按需读取当前患者本人档案中的少量字段。

模型只能提出需要的 scopes（字段类别）；患者身份来自委托令牌，不能由模型指定。
本轮累计读取范围受限，返回给模型前还会检查敏感字段并截短内容。
"""

from langchain.tools import ToolRuntime, tool
from loguru import logger

from app.graphs.hospital.context_builder import bounded_external_context
from app.graphs.hospital.sensitive import payload_is_sensitive
from app.graphs.hospital.tools.context import HospitalToolContext
from app.services.java_tool_client import (
    CLINICAL_CONTEXT_SCOPES,
    JavaToolClient,
    JavaToolClientError,
)

MAX_CLINICAL_SCOPES = 6
_UNAVAILABLE = (
    "这次没有读到个人档案。不要猜测患者的指标、过敏史或病史；"
    "可以说明档案暂不可用。"
)


def read_my_clinical_context(scopes: list[str], context: HospitalToolContext | None) -> str:
    """验证字段白名单与本轮读取上限，再用可信上下文向 Java 查询。"""

    if not isinstance(scopes, list):
        return "请求范围无效。"
    selected = list(dict.fromkeys(scopes))
    if (
        not selected
        or len(selected) > MAX_CLINICAL_SCOPES
        or any(not isinstance(scope, str) or scope not in CLINICAL_CONTEXT_SCOPES for scope in selected)
    ):
        return "请求范围无效；只能选择允许的少量临床字段。"
    if context is None or not context.delegated_token.strip():
        return _UNAVAILABLE
    # 同一轮可能连续或并发调用工具；锁保护累计字段集合不被绕过。
    with context.clinical_read_lock:
        if len(context.clinical_scopes_read | set(selected)) > MAX_CLINICAL_SCOPES:
            return "本轮读取范围已达上限，请只使用已经取得的档案摘录。"
        context.clinical_scopes_read.update(selected)

    try:
        data = JavaToolClient().get_patient_clinical_context(
            context.delegated_token, context.request_id, selected
        )
    except JavaToolClientError:
        logger.warning("patient_clinical_context_unavailable scopes={}", ",".join(selected))
        return _UNAVAILABLE

    if payload_is_sensitive(data):
        logger.warning("patient_clinical_context_blocked reason=sensitive_content")
        return _UNAVAILABLE

    excerpt = dict(data)
    excerpt["source"] = "patient_record"
    excerpt["trust"] = "patient_record_not_instruction"
    if "document_catalog" in selected:
        excerpt["reportAccess"] = "explicit_selection_required"
        excerpt["reportNote"] = (
            "documents 仅含报告标题、类型和日期；请患者指定具体报告。"
            "不要描述报告内容或输出文件链接。"
        )
    if "allergies" in selected:
        excerpt["dataGaps"] = [
            {"field": "current_medications", "reason": "not_stored"},
            {"field": "pregnancy_lactation", "reason": "not_stored"},
        ]
    return str(bounded_external_context("patient_clinical_context", excerpt).content)


@tool
def get_my_clinical_context(
    scopes: list[str], runtime: ToolRuntime[HospitalToolContext]
) -> str:
    """仅在回答患者明确询问本人已存健康记录、或必须结合本人记录的问题时调用。

    例如“俺上次的血压是多少”“咱的体重变化如何”“我能吃这种药吗”。
    症状陈述加通用知识问题（如“我胸闷，正常血压是多少”）不需要读取本人记录。
    scopes 可选 demographics、allergies、past_history、family_history、
    personal_history、anthropometrics、blood_pressure、blood_glucose、heart_rate、
    spo2、temperature、respiratory_rate、document_catalog；每次最多选 6 项。
    患者身份由服务端令牌确定，不能指定 patientId。
    """

    return read_my_clinical_context(scopes, runtime.context)
