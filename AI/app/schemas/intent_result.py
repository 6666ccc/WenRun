from pydantic import BaseModel, Field
from typing import Literal

class IntentResult(BaseModel):
    intent: Literal["chat", "tool", "knowledge"] = Field(
        description=(
            "chat=闲聊问候；"
            "tool=挂号/查号源/查账单等办事；"
            "knowledge=医疗知识/症状科普/就诊须知"
        )
    )