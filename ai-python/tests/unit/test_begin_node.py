from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.graphs.hospital.nodes import begin


class StubModel:
    def __init__(self, responses: list[AIMessage | Exception]):
        self.responses = responses
        self.calls: list[list] = []

    def invoke(self, messages):
        self.calls.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_begin_node_uses_model_json_without_tool_strategy(monkeypatch):
    stub_model = StubModel(
        [AIMessage(content='{"selected_agents":["knowledge","tools"]}')]
    )
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="我感冒了，帮我挂明天内科")]})

    assert result == {"selected_agents": ["knowledge", "tools"]}
    assert len(stub_model.calls) == 1
    assert isinstance(stub_model.calls[0][0], SystemMessage)
    assert "只返回一个 JSON 对象" in stub_model.calls[0][0].content


def test_begin_node_asks_model_to_repair_invalid_json_once(monkeypatch):
    stub_model = StubModel(
        [
            AIMessage(content="我建议走 knowledge"),
            AIMessage(content='{"selected_agents":["knowledge"]}'),
        ]
    )
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="普通感冒有什么症状")]})

    assert result == {"selected_agents": ["knowledge"]}
    assert len(stub_model.calls) == 2
    assert isinstance(stub_model.calls[1][0], SystemMessage)
    assert "上一次无效输出如下" in stub_model.calls[1][0].content


def test_begin_node_falls_back_to_chat_after_invalid_repair(monkeypatch):
    stub_model = StubModel(
        [AIMessage(content='{"selected_agents":["other"]}'), AIMessage(content="[]")]
    )
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="随便说点什么")]})

    assert result == {"selected_agents": ["chat"]}
    assert len(stub_model.calls) == 2


def test_begin_node_retries_once_when_model_call_fails(monkeypatch):
    stub_model = StubModel(
        [RuntimeError("temporary error"), AIMessage(content='{"selected_agents":["chat"]}')]
    )
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node({"messages": [HumanMessage(content="你好")]})

    assert result == {"selected_agents": ["chat"]}
    assert len(stub_model.calls) == 2
