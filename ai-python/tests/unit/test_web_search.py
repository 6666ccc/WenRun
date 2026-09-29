from app.graphs.hospital.tools.search import (
    format_search_results,
    search_web,
    web_search,
)


def test_format_search_results_numbers_title_url_and_snippet():
    text = format_search_results(
        [
            {
                "title": "感冒护理",
                "url": "https://example.com/cold",
                "content": "多休息、多饮水。",
            }
        ]
    )

    assert "[1] 感冒护理" in text
    assert "https://example.com/cold" in text
    assert "多休息、多饮水。" in text


def test_format_search_results_empty_is_blank():
    assert format_search_results([]) == ""


def test_search_web_maps_tavily_results(monkeypatch):
    class FakeClient:
        def __init__(self, api_key: str) -> None:
            assert api_key == "tvly-test"

        def search(self, query: str, max_results: int = 5, search_depth: str = "basic", timeout: float = 60):
            assert query == "感冒吃什么药"
            assert max_results == 5
            assert timeout == 20
            return {
                "results": [
                    {
                        "title": "用药说明",
                        "url": "https://example.com/meds",
                        "content": "对症处理",
                    }
                ]
            }

    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.setattr(
        "app.graphs.hospital.tools.search.TavilyClient",
        FakeClient,
    )

    assert search_web("感冒吃什么药") == [
        {
            "title": "用药说明",
            "url": "https://example.com/meds",
            "content": "对症处理",
        }
    ]


def test_search_web_without_api_key_returns_empty(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert search_web("儿科在几楼") == []


def test_web_search_tool_uses_formatted_results(monkeypatch):
    monkeypatch.setattr(
        "app.graphs.hospital.tools.search.search_web",
        lambda query, max_results=5: [
            {
                "title": "感冒护理",
                "url": "https://example.com/cold",
                "content": "多休息。",
            }
        ],
    )
    text = web_search.invoke({"query": "感冒吃什么药"})
    assert "[1] 感冒护理" in text
    assert "https://example.com/cold" in text


def test_search_failure_is_reported_without_aborting_the_agent(monkeypatch):
    from app.observability import progress

    events = []
    monkeypatch.setattr(progress, "get_stream_writer", lambda: events.append)

    def unavailable(*args, **kwargs):
        raise TimeoutError("SECRET provider details")

    monkeypatch.setattr("app.graphs.hospital.tools.search.search_web", unavailable)
    reply = web_search.invoke({"query": "胃胀反酸"})
    assert reply.startswith("暂时无法查询")
    assert "SECRET" not in reply
    assert events[-1]["step"]["status"] == "failed"
