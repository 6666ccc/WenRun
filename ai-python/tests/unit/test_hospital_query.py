from datetime import date

from app.graphs.hospital.nodes.hospital_query import extract_hospital_query, select_slot


def test_extracts_tomorrow_afternoon_and_surgery_dept():
    query = extract_hospital_query("外科在哪里，明天下午有哪些医生", today=date(2026, 8, 16))
    assert query["dept_name"] == "外科"
    assert query["work_date"] == "2026-08-17"
    assert query["time_period"] == "下午"
    assert query["staff_name"] is None


def test_extracts_first_ordinal():
    query = extract_hospital_query("挂第一个号源")
    assert query["ordinal"] == 1


def test_select_slot_asks_when_candidates_are_not_unique():
    schedules = [
        {"id": 1, "staffName": "李医生", "timePeriod": "下午"},
        {"id": 2, "staffName": "王医生", "timePeriod": "下午"},
    ]
    slot, filtered = select_slot(schedules, {"time_period": "下午"})
    assert slot is None
    assert len(filtered) == 2


def test_select_slot_uses_ordinal_when_multiple_candidates():
    schedules = [
        {"id": 1, "staffName": "李医生"},
        {"id": 2, "staffName": "王医生"},
    ]
    slot, filtered = select_slot(schedules, {"ordinal": 1})
    assert slot["id"] == 1
    assert len(filtered) == 2
