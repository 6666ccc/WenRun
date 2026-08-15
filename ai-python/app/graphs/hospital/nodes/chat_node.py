"""
这是一个聊天节点，用于处理聊天相关的任务
"""

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from app.graphs.hospital.state import State
import os



model = ChatOpenAI(
    model=os.getenv("DASHSCOPE_CHAT_MODEL"),
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)

agent = create_agent(
    model=model,
    system_prompt="你的主要任务是和患者进行聊天, 必须要有耐心和同理心。",
)


def chat_node(state: State) -> dict:
    last = state["messages"][-1]
    response = agent.invoke({
        "messages": [{"role": "user", "content": last.content}]
    })
    return {"messages": [response["messages"][-1]]}  # 只追加助手回复
