from langchain_core.messages import AIMessage


class FixedIntentAgent:
    def __init__(self, intent: str | None):
        self.intent = intent

    def invoke(self, payload):
        from app.models.intent_result import IntentResult

        if self.intent is None:
            return {}
        return {"structured_response": IntentResult(intent=self.intent)}


class FakeReplyAgent:
    def __init__(self, text: str):
        self.text = text

    def invoke(self, payload):
        return {"messages": [AIMessage(content=self.text)]}


def _deps(intent: str | None, fake_medical_agent):
    from app.graphs.hospital.graph import GraphDependencies

    return GraphDependencies(
        intent_agent=FixedIntentAgent(intent),
        chat_agent=FakeReplyAgent("chat-reply"),
        hospital_agent=FakeReplyAgent("hospital-reply"),
        medical_agent=fake_medical_agent,
        clarify_agent=FakeReplyAgent("clarify-reply"),
        hospital_retriever=None,
        medical_retriever=None,
        tools=None,
    )


def _base_state(message: str) -> dict:
    return {
        "messages": [{"role": "user", "content": message}],
        "conversation_id": "conv-1",
        "user_id": 1,
        "patient_id": 10,
        "intent": None,
        "memory_enabled": True,
        "task_plan": [],
        "tool_context": {},
        "sources": [],
        "pending_action": None,
        "error": None,
        "retry_count": 0,
    }


def _visited_nodes(graph, message: str) -> list[str]:
    visited: list[str] = []
    for event in graph.stream(_base_state(message), stream_mode="updates"):
        visited.extend(event.keys())
    return visited


def _assert_reaches_citation_validate(visited: list[str], business_node: str) -> None:
    assert business_node in visited
    assert "citation_validate" in visited
    assert visited.index("citation_validate") == visited.index(business_node) + 1
    assert "save_memory" in visited
    assert visited.index("save_memory") == visited.index("citation_validate") + 1


def test_chat_path_reaches_citation_validate(fake_medical_agent):
    from app.graphs.hospital.graph import build_graph

    graph = build_graph(_deps("chat", fake_medical_agent))
    visited = _visited_nodes(graph, "你好")
    _assert_reaches_citation_validate(visited, "chat")
    result = graph.invoke(_base_state("你好"))
    assert result["messages"][-1].content == "chat-reply"
    assert result["intent"] == "chat"


def test_hospital_path_reaches_citation_validate(fake_medical_agent):
    from app.graphs.hospital.graph import build_graph

    graph = build_graph(_deps("hospital", fake_medical_agent))
    visited = _visited_nodes(graph, "外科在哪里，顺便帮我挂号")
    _assert_reaches_citation_validate(visited, "hospital")
    result = graph.invoke(_base_state("外科在哪里，顺便帮我挂号"))
    assert result["messages"][-1].content == "hospital-reply"
    assert result["intent"] == "hospital"


def test_medical_path_reaches_citation_validate(fake_medical_agent):
    from app.graphs.hospital.graph import build_graph

    graph = build_graph(_deps("medical", fake_medical_agent))
    visited = _visited_nodes(graph, "胸痛并且呼吸困难")
    _assert_reaches_citation_validate(visited, "medical")
    result = graph.invoke(_base_state("胸痛并且呼吸困难"))
    answer = result["messages"][-1].content
    assert "急诊" in answer or "急救" in answer
    assert "确诊" not in answer
    assert result["intent"] == "medical"


def test_unclear_intent_uses_clarify_then_citation_validate(fake_medical_agent):
    from app.graphs.hospital.graph import build_graph

    graph = build_graph(_deps(None, fake_medical_agent))
    visited = _visited_nodes(graph, "那个怎么弄")
    _assert_reaches_citation_validate(visited, "clarify")
    result = graph.invoke(_base_state("那个怎么弄"))
    assert result["messages"][-1].content == "clarify-reply"
    assert result["intent"] is None


def test_business_nodes_do_not_edge_directly_to_end(fake_medical_agent):
    from app.graphs.hospital.graph import build_graph

    compiled = build_graph(_deps("chat", fake_medical_agent))
    edges = {(edge.source, edge.target) for edge in compiled.get_graph().edges}
    for node in ("chat", "hospital", "medical", "clarify"):
        assert (node, "citation_validate") in edges
        assert (node, "__end__") not in edges


def test_build_graph_does_not_construct_external_clients(fake_medical_agent, monkeypatch):
    from app.graphs.hospital.graph import build_graph

    def boom(*args, **kwargs):
        raise AssertionError("tests must not construct DashScope or Qdrant clients")

    monkeypatch.setattr("langchain_openai.ChatOpenAI", boom)
    monkeypatch.setattr("langchain_openai.OpenAIEmbeddings", boom)
    graph = build_graph(_deps("chat", fake_medical_agent))
    assert graph is not None
    graph.invoke(_base_state("你好"))
