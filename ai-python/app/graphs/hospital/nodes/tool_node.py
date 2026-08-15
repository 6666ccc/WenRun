"""工具节点"""
import os
from langchain_openai import ChatOpenAI  
from langchain.agents import create_agent
from app.graphs.hospital.tools.test_tool import test_tool
from app.graphs.hospital.state import State

model = ChatOpenAI(
    model=os.getenv("DASHSCOPE_CHAT_MODEL"),
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)

agent = create_agent(
    model=model,
    system_prompt="你的主要任务是回答用户关于工具使用的问题。你是专业的工具使用专家，你的回答需要准确、专业、详细。",
    tools=[test_tool],
)


def tool_node(state: State) -> dict:
    last = state["messages"][-1]
    response = agent.invoke({
        "messages": [{"role": "user", "content": last.content}]
    })
    return {"messages": [response["messages"][-1]]}  
