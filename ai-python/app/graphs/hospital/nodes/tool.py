"""该文件主要构建tool_agent"""
## 待办
from app.models.chat import model
from langchain.agents import create_agent

agent = create_agent(
    model= model,
    tools=[],
    system_prompt=""
)
