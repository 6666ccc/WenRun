from app.services.java_tools.client import JavaToolsClient
from app.services.java_tools.dept import query_depts
from app.services.java_tools.doctor import query_doctors
from app.services.java_tools.registration import create_registration
from app.services.java_tools.schedule import query_schedules


class JavaHospitalTools:
    """Hospital node adapter: method names match the controlled tool plan."""

    def __init__(self, client: JavaToolsClient):
        self.client = client

    def query_depts(self, token=None, status=None, **_kwargs):
        return query_depts(self.client, token, status=status)

    def query_doctors(self, token=None, dept_id=None, **_kwargs):
        return query_doctors(self.client, token, dept_id=dept_id)

    def query_schedules(self, token=None, dept_id=None, work_date=None, staff_id=None, **_kwargs):
        return query_schedules(
            self.client,
            token,
            dept_id=dept_id,
            work_date=work_date,
            staff_id=staff_id,
        )

    def create_registration(self, token=None, **payload):
        return create_registration(self.client, token, payload)
