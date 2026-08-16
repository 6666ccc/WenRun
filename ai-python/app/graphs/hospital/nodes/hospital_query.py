"""从患者话术中提取挂号查询参数，并在号源不唯一时避免擅自选择。"""

from __future__ import annotations

import re
from datetime import date, timedelta

DEPT_TOKENS = (
    "耳鼻喉科",
    "妇产科",
    "口腔科",
    "皮肤科",
    "中医科",
    "眼科",
    "骨科",
    "儿科",
    "外科",
    "内科",
    "急诊",
    "口腔",
)
CN_ORDINALS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
STAFF_RE = re.compile(r"([\u4e00-\u9fff]{1,3})(?:医生|大夫)")
ORDINAL_RE = re.compile(r"第([一二两三四五六七八九十\d]+)个")


def extract_hospital_query(text: str, today: date | None = None) -> dict:
    source = text or ""
    today = today or date.today()
    work_date = None
    if "明天" in source:
        work_date = (today + timedelta(days=1)).isoformat()
    elif "今天" in source:
        work_date = today.isoformat()
    elif "后天" in source:
        work_date = (today + timedelta(days=2)).isoformat()

    time_period = None
    for token in ("上午", "下午", "晚上"):
        if token in source:
            time_period = token
            break

    dept_name = next((token for token in DEPT_TOKENS if token in source), None)
    if dept_name == "口腔":
        dept_name = "口腔科"

    staff_match = STAFF_RE.search(source)
    staff_name = staff_match.group(1) if staff_match else None
    if staff_name and any(token in staff_name for token in ("哪", "什", "几")):
        staff_name = None
    ordinal = None
    ordinal_match = ORDINAL_RE.search(source)
    if ordinal_match:
        raw = ordinal_match.group(1)
        ordinal = int(raw) if raw.isdigit() else CN_ORDINALS.get(raw)
    elif "第一" in source:
        ordinal = 1

    return {
        "dept_name": dept_name,
        "work_date": work_date,
        "time_period": time_period,
        "staff_name": staff_name,
        "ordinal": ordinal,
    }


def match_dept_id(depts: list | None, dept_name: str | None):
    if not dept_name:
        return None
    for item in depts or []:
        name = str(item.get("deptName") or item.get("name") or "")
        if dept_name in name or name in dept_name:
            return item.get("id")
    return None


def filter_schedules(schedules: list | None, query: dict) -> list:
    result = list(schedules or [])
    period = query.get("time_period")
    if period:
        result = [item for item in result if period in str(item.get("timePeriod") or "")]
    staff_name = query.get("staff_name")
    if staff_name:
        result = [item for item in result if staff_name in str(item.get("staffName") or "")]
    return result


def select_slot(schedules: list | None, query: dict) -> tuple[dict | None, list]:
    filtered = filter_schedules(schedules, query)
    if not filtered:
        return None, filtered
    ordinal = query.get("ordinal")
    if isinstance(ordinal, int) and 1 <= ordinal <= len(filtered):
        return filtered[ordinal - 1], filtered
    if len(filtered) == 1:
        return filtered[0], filtered
    return None, filtered


def format_slot_choices(schedules: list) -> str:
    lines = []
    for index, item in enumerate(schedules, start=1):
        lines.append(
            f"{index}. {item.get('deptName') or '科室未指定'} "
            f"{item.get('staffName') or '医生未指定'}，"
            f"{item.get('workDate')} {item.get('timePeriod')}，"
            f"余号{item.get('remainingCount', '未知')}，费用{item.get('registerFee')}"
        )
    return "当前有多个可挂号源，请回复序号或医生姓名进行选择：\n" + "\n".join(lines)
