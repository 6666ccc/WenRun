SAFE_MESSAGES = {
    "SCHEDULE_NOT_FOUND": "未找到对应排班，请重新选择。",
    "SLOT_SOLD_OUT": "该号源已满，请选择其他时段。",
    "DUPLICATE_REGISTRATION": "您已挂过该号源，无需重复提交。",
    "INVALID_PATIENT": "患者信息不匹配，请重新登录后再试。",
    "INSUFFICIENT_SCOPE": "当前授权不足以完成该操作。",
    "INTERRUPT_MISMATCH": "确认信息已失效，请重新发起挂号。",
    "JAVA_TOOL_TIMEOUT": "医院系统响应超时，请稍后重试。",
    "JAVA_TOOL_UNAVAILABLE": "医院系统暂时不可用，请稍后重试。",
}


class ToolFailure(Exception):
    def __init__(self, code: str, safe_message: str, retryable: bool = False):
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable
