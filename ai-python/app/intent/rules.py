"""高精度路由规则。

这里只放能够明确决定路径的规则。模糊关键词留给轻量模型或 LLM，避免把
正则表演变成另一套难以维护的自然语言分类器。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.graphs.hospital.state import AgentName


@dataclass(frozen=True)
class RuleMatch:
    selected_agents: list[AgentName]
    matched_rules: list[str]
    safety_flags: list[str]


def normalize_text(text: str) -> str:
    """统一全半角、大小写和空白，供规则与轻量模型共用。"""

    normalized = unicodedata.normalize("NFKC", text).lower().strip()
    return re.sub(r"\s+", " ", normalized)


_URGENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("breathing_difficulty", re.compile(r"呼吸困难|喘不上气|无法呼吸|不能呼吸")),
    ("severe_bleeding", re.compile(r"大出血|血流不止|止不住血")),
    ("loss_of_consciousness", re.compile(r"失去意识|意识不清|昏迷|叫不醒")),
    ("possible_stroke", re.compile(r"嘴歪|口角歪斜|一侧肢体无力|言语不清")),
    ("self_harm", re.compile(r"想自杀|不想活了|伤害自己|结束生命")),
    (
        "acute_chest_pain",
        re.compile(r"(?:突然|剧烈|持续).{0,6}胸痛|胸痛.{0,8}(?:呼吸困难|大汗|晕厥)"),
    ),
)

_EXACT_CHAT = re.compile(
    r"^(?:你?好|您好|嗨|哈[喽啰]|早上好|下午好|晚上好|谢谢(?:你|您)?(?:了|啊)?|"
    r"多谢|再见|拜拜|晚安)[!！。,.?？，~～ ]*$"
)
_IDENTITY_MENTION = re.compile(
    r"你是谁|你叫什么(?:名字)?|你能做什么|你会干什么|能干什么|介绍一下(?:你|您)自己"
)
_EXACT_IDENTITY = re.compile(
    r"^(?:请问|请告诉我)?"
    r"(?:"
    r"你是谁|"
    r"你叫什么(?:名字)?|"
    r"你能做什么|"
    r"你会干什么|"
    r"介绍一下(?:你|您)自己|"
    r"你是什么(?:助手|模型)?"
    r")"
    r"(?:啊|呀|呢|嘛)?"
    r"[!！。,.?？~～ ]*$"
)
_EXACT_CLOCK_QUESTION = re.compile(
    r"^(?:你?好[,， ]*)?(?:请问|请告诉我|麻烦问下|麻烦问一下)?"
    r"(?:现在|当前|目前)?"
    r"(?:是)?"
    r"(?:"
    r"几点(?:钟)?了?|"
    r"今天(?:是)?(?:几号|星期几|周几|礼拜几)|"
    r"星期几了?"
    r")"
    r"(?:啊|呀|呢|嘛)?"
    r"[!！。,.?？~～ ]*$"
)
_HOSPITAL_STATIC = re.compile(
    r"(?:医院|诊所|门诊|前台|[\u4e00-\u9fff]{1,6}科(?:室)?).{0,8}"
    r"(?:几楼|哪一层|怎么走|在哪里|在哪儿|地址|营业时间|几点(?:开门|关门|下班)|停车)|"
    r"(?:几楼|哪一层|营业时间|几点(?:开门|关门|下班)|就诊须知|医院地址|诊所地址|"
    r"医院停车|门诊停车|公交到医院|地铁到医院)"
)
_DEPARTMENT_CATALOG = re.compile(
    r"(?:有|开设|能看|可以看|都有什么|都有哪些|哪些|什么).{0,5}科(?:室)?|"
    r"科(?:室)?(?:有|包括|列表|目录)哪些?"
)
_APPOINTMENT_ACTION = re.compile(
    r"(?:帮我|给我|我要|想|需要|请).{0,8}(?:挂号|挂个号|预约|退号|取消预约)|"
    r"(?:帮我|给我|请).{0,3}挂.{0,8}(?:今天|明天|后天|本周|下周|周[一二三四五六日天]|科|医生)|"
    r"(?:挂号|预约|退号|取消预约).{0,8}(?:怎么|如何|一下|办理)"
)
_REALTIME_BUSINESS = re.compile(
    r"(?:号源|余号|有没有号|还有号吗|排班|出诊|坐诊|我的预约|我的挂号|"
    r"挂号记录|预约记录)"
)
_MEMORY_ACTION = re.compile(
    r"(?:请|帮我|以后)?(?:记住|记一下|保存这个偏好)|"
    r"(?:忘掉|忘记|删除|清除).{0,20}(?:偏好|记忆|习惯|称呼)"
)
_EXPLICIT_MEDICAL = re.compile(
    r"(?:吃|服|用).{0,5}(?:什么药|药量|剂量)|药.{0,5}(?:副作用|禁忌|能不能吃)|"
    r"(?:症状|病情|发烧|咳嗽|头痛|腹痛|肚子痛|胸痛|恶心|呕吐|腹泻).{0,10}"
    r"(?:怎么办|怎么处理|是否严重|要不要就医|需要就医|吃什么药)|"
    r"(?:什么病|什么症状|如何护理|怎么护理|注意事项)|"
    r"(?:有哪些|有什么|是什么|哪些).{0,6}症状|"
    r"的症状"
)
_MEDICAL_CONTEXT = re.compile(
    r"感冒|发烧|咳嗽|头痛|腹痛|肚子痛|胃痛|胃疼|胸痛|恶心|呕吐|腹泻|"
    r"皮疹|过敏|失眠|不舒服|疼|痛|药|症状"
)
_DEPARTMENT_RECOMMENDATION = re.compile(r"(?:该|要|应该|建议)?看(?:哪|哪个|什么|哪一)科|挂什么科")


def detect_safety_flags(text: str) -> list[str]:
    normalized = normalize_text(text)
    return [name for name, pattern in _URGENT_PATTERNS if pattern.search(normalized)]


def match_rules(text: str) -> RuleMatch | None:
    """返回可直接采用的规则结果；没有强匹配时返回 ``None``。"""

    normalized = normalize_text(text)
    if not normalized:
        return None

    safety_flags = detect_safety_flags(normalized)
    matched_rules: list[str] = []
    selected: list[AgentName] = []

    def select(agent: AgentName, rule: str) -> None:
        if agent not in selected:
            selected.append(agent)
        matched_rules.append(rule)

    # 安全信号是正交维度：它强制保留医疗知识路径，但不吞掉同句中的挂号请求。
    if safety_flags:
        select("knowledge", "urgent_safety")

    if _DEPARTMENT_CATALOG.search(normalized):
        select("tools", "department_catalog")
    if _APPOINTMENT_ACTION.search(normalized):
        select("tools", "appointment_action")
    if _REALTIME_BUSINESS.search(normalized):
        select("tools", "realtime_business")
    if _MEMORY_ACTION.search(normalized):
        select("tools", "memory_action")
    if _EXPLICIT_MEDICAL.search(normalized):
        select("knowledge", "explicit_medical_question")
    if _DEPARTMENT_RECOMMENDATION.search(normalized):
        # “该看哪科”既需要医疗分科知识，也需要实时科室目录。
        select("knowledge", "department_recommendation")
        select("tools", "department_recommendation")

    # 症状陈述本身可能省略问号；当同句明确办理业务时保留医疗知识路径。
    if "tools" in selected and _MEDICAL_CONTEXT.search(normalized):
        select("knowledge", "medical_context_with_business")

    if selected and _IDENTITY_MENTION.search(normalized):
        select("chat", "identity_with_other_intents")

    if selected:
        return RuleMatch(selected, matched_rules, safety_flags)

    if _EXACT_CHAT.fullmatch(normalized):
        return RuleMatch(["chat"], ["exact_social"], safety_flags)

    if _EXACT_IDENTITY.fullmatch(normalized):
        return RuleMatch(["chat"], ["exact_identity"], safety_flags)

    if _EXACT_CLOCK_QUESTION.fullmatch(normalized):
        return RuleMatch(["chat"], ["exact_clock_question"], safety_flags)

    if _HOSPITAL_STATIC.search(normalized):
        return RuleMatch(["chat"], ["hospital_static_information"], safety_flags)

    return None
