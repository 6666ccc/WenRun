from app.core.config import Settings


def test_settings_define_isolated_collections():
    settings = Settings(
        dashscope_api_key="test",
        dashscope_base_url="https://example.invalid/v1",
        dashscope_chat_model="test-model",
        embedding_model="test-embedding",
        internal_api_key="internal",
    )
    assert settings.hospital_collection == "wenrun_hospital_custom"
    assert settings.medical_collection == "wenrun_medical_general"
    assert settings.memory_collection == "wenrun_conversation_memory"
    assert settings.checkpoint_path.endswith(".sqlite")
