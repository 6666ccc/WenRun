def query_depts(client, token: str, status=None):
    params = f"?status={status}" if status is not None else ""
    return client.request("GET", f"/api/internal/ai-tools/depts{params}", token) or []
