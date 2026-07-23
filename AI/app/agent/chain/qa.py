from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

import os
from dotenv import load_dotenv

load_dotenv()

model = ChatOpenAI(
    model=os.getenv("DASHSCOPE_CHAT_MODEL"),
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)

agent = create_agent(
    model=model,
    tools=[],
    system_prompt="You are a helpful assistant that can answer questions and help with tasks."
)


def get_answer(question: str) -> str:
    response = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return response["messages"][-1].content
