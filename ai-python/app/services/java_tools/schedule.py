def query_schedules(client, token: str, dept_id=None, work_date=None, staff_id=None):
    parts = []
    if dept_id is not None:
        parts.append(f"deptId={dept_id}")
    if work_date is not None:
        parts.append(f"workDate={work_date}")
    if staff_id is not None:
        parts.append(f"staffId={staff_id}")
    query = f"?{'&'.join(parts)}" if parts else ""
    return client.request("GET", f"/api/internal/ai-tools/schedules{query}", token) or []
