from app.services.java_tools.facade import JavaHospitalTools


class FakeClient:
    def __init__(self):
        self.calls = []

    def request(self, method, path, token, json=None):
        self.calls.append((method, path, token, json))
        return []


def test_facade_query_schedules_forwards_filters():
    client = FakeClient()
    tools = JavaHospitalTools(client)
    tools.query_schedules(token="t", dept_id=3, work_date="2026-08-17")
    method, path, token, _payload = client.calls[0]
    assert method == "GET"
    assert token == "t"
    assert "deptId=3" in path
    assert "workDate=2026-08-17" in path
    assert path.startswith("/api/internal/ai-tools/schedules")
