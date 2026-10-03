from langchain_core.messages import HumanMessage

from app.graphs.hospital.context_builder import build_context
from app.graphs.hospital.nodes.knowledge import necessary_clinical_scopes
from app.graphs.hospital.tools.medical_source import is_authoritative_url


def test_personal_body_and_drug_read_minimum_scopes():
    assert necessary_clinical_scopes("我的档案体重是多少") == ["anthropometrics"]
    assert necessary_clinical_scopes("我能吃这种药吗") == ["demographics", "allergies"]
    assert necessary_clinical_scopes("根据我的体重计算药物剂量") == [
        "demographics",
        "allergies",
        "anthropometrics",
    ]
    assert necessary_clinical_scopes("我胸闷，正常血压是多少") == []


def test_authority_url_not_substring_or_local_host():
    assert is_authoritative_url("https://www.fda.gov/drugs/example")
    for url in [
        "https://fda.gov.evil.test/",
        "http://localhost/",
        "https://fda.gov@evil.test/",
        "http://fda.gov/",
        "https://fda.gov:invalid/",
        "https://[invalid/",
    ]:
        assert not is_authoritative_url(url)


def test_expired_preferences_are_not_injected():
    output = build_context(
        {
            "messages": [HumanMessage(content="你好")],
            "long_term_memories": [
                {
                    "type": "communication_preference",
                    "content": "已经到期的大字偏好",
                    "expireTime": "2000-01-01T12:00:00",
                }
            ],
        },
        purpose="chat",
    )
    assert "已经到期的大字偏好" not in str(output)
