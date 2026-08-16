from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.core.config import Settings


def create_chat_model(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.dashscope_chat_model,
        base_url=settings.dashscope_base_url,
        api_key=settings.dashscope_api_key,
    )


def create_embeddings(settings: Settings) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        base_url=settings.dashscope_base_url,
        api_key=settings.dashscope_api_key,
    )
