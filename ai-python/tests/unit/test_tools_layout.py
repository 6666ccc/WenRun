import importlib

import pytest


def test_hospital_graph_tools_export_langchain_tools():
    hospital_tools = importlib.import_module("app.graphs.hospital.tools")

    assert hospital_tools.search_hospital_knowledge.name == "search_hospital_knowledge"
    assert hospital_tools.web_search.name == "web_search"
    assert hospital_tools.list_departments.name == "list_departments"
    assert hospital_tools.list_doctors.name == "list_doctors"
    assert hospital_tools.list_schedules.name == "list_schedules"
    assert hospital_tools.list_my_registrations.name == "list_my_registrations"
    assert hospital_tools.create_registration.name == "create_registration"
    assert hospital_tools.cancel_registration.name == "cancel_registration"
    assert hospital_tools.HospitalToolContext("token", "trace").delegated_token == "token"


def test_java_http_client_lives_in_services_not_app_tools():
    from app.services.java_tool_client import JavaToolClient

    assert JavaToolClient.__name__ == "JavaToolClient"
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.tools.java_tool_client")
