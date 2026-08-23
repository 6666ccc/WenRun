from app.graphs.hospital.tools.web_search import (
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

        def search(self, query: str, max_results: int = 5, search_depth: str = "basic"):
            assert query == "感冒吃什么药"
            assert max_results == 5
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
        "app.graphs.hospital.tools.web_search.TavilyClient",
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
        "app.graphs.hospital.tools.web_search.search_web",
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
