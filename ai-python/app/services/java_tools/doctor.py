def query_doctors(client, token: str, dept_id=None):
    query = f"?deptId={dept_id}" if dept_id is not None else ""
    return client.request("GET", f"/api/internal/ai-tools/staff{query}", token) or []
