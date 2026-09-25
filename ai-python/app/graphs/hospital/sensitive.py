"""防止证件号、电话、地址和文件链接进入模型上下文或长期摘要。"""

import re

_SECRET = re.compile(
    r"https?://\S+|cos://\S+|(?<!\d)\d{17}[\dXx](?!\d)|(?<!\d)1[3-9]\d{9}(?!\d)",
    re.IGNORECASE,
)
_ADDRESS = re.compile(r"[\u4e00-\u9fff]{1,12}(?:省|市).{0,40}(?:路|街|巷|道|号|室)")
_FORBIDDEN_KEYS = frozenset({
    "idcard",
    "id_card",
    "phone",
    "mobile",
    "address",
    "patientno",
    "patient_no",
    "birthdate",
    "birth_date",
    "name",
    "fullname",
    "patientname",
    "patient_name",
    "cosurl",
    "cos_url",
    "signedurl",
    "signed_url",
    "fileurl",
    "file_url",
    "filesjson",
    "files_json",
    "url",
})


def redact_sensitive(value: str) -> str:
    """把文本中可识别的敏感片段替换成“已省略”。"""
    text = _SECRET.sub("[已省略]", value)
    return _ADDRESS.sub("[已省略]", text)


def contains_sensitive(value: str) -> bool:
    """判断文本是否包含目前规则能识别的敏感片段。"""
    return redact_sensitive(value) != value


def cleaned_memory_text(value: str) -> str | None:
    """清理摘要文本；若只剩被遮盖的内容就丢弃该条。"""
    text = redact_sensitive(value).strip()
    if not text or text.replace("[已省略]", "").strip() == "":
        return None
    return text


def payload_is_sensitive(value: object) -> bool:
    """递归检查对象的字段名与文本，阻止整份敏感数据进入模型。"""
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS or payload_is_sensitive(item):
                return True
        return False
    if isinstance(value, list):
        return any(payload_is_sensitive(item) for item in value)
    if isinstance(value, str):
        return contains_sensitive(value)
    return False
