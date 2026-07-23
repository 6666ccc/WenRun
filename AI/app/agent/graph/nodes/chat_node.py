"""
这是一个聊天节点，用于处理聊天相关的任务
"""

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
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
