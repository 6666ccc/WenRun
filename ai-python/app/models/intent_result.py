from typing import Literal

from pydantic import BaseModel, Field


class IntentResult(BaseModel):
    intent: Literal["chat", "hospital", "medical"] = Field(
        description=(
            "chat=问候、闲聊、倾听、情绪陪伴；"
            "hospital=医院信息、科室、医资、挂号及其他院内办事；"
            "混合“医院信息 + 办事”属于 hospital；"
            "medical=疾病、症状、日常护理、健康科普"
        )
    )
