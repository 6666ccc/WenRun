"""医疗知识节点"""
import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent


model = ChatOpenAI(
  model=os.getenv("DASHSCOPE_CHAT_MODEL"),
  base_url=os.getenv("DASHSCOPE_BASE_URL"),
  api_key=os.getenv("DASHSCOPE_API_KEY"),
)

agent = create_agent(
  model=model,
  system_prompt="你的主要任务是回答用户关于医疗知识的问题。你是专业的医疗知识专家，你的回答需要准确、专业、详细。",
)