from app.graphs.hospital.nodes.citation_validate_node import citation_validate_node


def test_unsupported_claim_is_rejected():
    state = {
        "messages": [{"role": "assistant", "content": "本院每天七点挂号 [S1]"}],
        "sources": [{"id": "S1", "excerpt": "门诊八点开始挂号"}],
        "retry_count": 1,
    }
    result = citation_validate_node(state)
    assert result["error"]["code"] == "UNSUPPORTED_CITATION"


def test_first_failure_asks_for_rewrite():
    state = {
        "messages": [{"role": "assistant", "content": "本院每天七点挂号 [S1]"}],
        "sources": [{"id": "S1", "excerpt": "门诊八点开始挂号"}],
        "retry_count": 0,
        "intent": "hospital",
    }
    result = citation_validate_node(state)
    assert result.get("retry_count") == 1
    assert "error" not in result or result.get("error") is None
    texts = [_message_text(item) for item in result.get("messages", [])]
    assert any("重写" in text for text in texts)


def test_chat_answer_without_citations_passes():
    state = {
        "messages": [{"role": "assistant", "content": "你好，我在，今天想聊点什么？"}],
        "sources": [],
        "intent": "chat",
        "retry_count": 0,
    }
    result = citation_validate_node(state)
    assert not result.get("error")
    assert not result.get("needs_rewrite")


def test_missing_citation_id_is_rejected_on_second_failure():
    state = {
        "messages": [{"role": "assistant", "content": "外科在一楼 [S9]"}],
        "sources": [{"id": "S1", "excerpt": "外科在门诊楼一层"}],
        "retry_count": 1,
        "intent": "hospital",
    }
    result = citation_validate_node(state)
    assert result["error"]["code"] == "UNSUPPORTED_CITATION"


def test_wrong_knowledge_base_is_rejected():
    state = {
        "messages": [{"role": "assistant", "content": "口腔溃疡多与免疫有关 [S1]"}],
        "sources": [{
            "id": "S1",
            "excerpt": "口腔溃疡多与免疫有关",
            "knowledgeBase": "hospital-custom",
        }],
        "retry_count": 1,
        "intent": "medical",
    }
    result = citation_validate_node(state)
    assert result["error"]["code"] == "UNSUPPORTED_CITATION"


def test_supported_claim_passes():
    state = {
        "messages": [{"role": "assistant", "content": "门诊八点开始挂号 [S1]"}],
        "sources": [{"id": "S1", "excerpt": "门诊八点开始挂号", "knowledgeBase": "hospital-custom"}],
        "retry_count": 0,
        "intent": "hospital",
    }
    result = citation_validate_node(state)
    assert not result.get("error")
    assert not result.get("needs_rewrite")


def _message_text(message) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")
