"""意图判断节点"""

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from app.models.intent_result import IntentResult
from langgraph.graph import MessagesState
from loguru import logger as log
import os

model = ChatOpenAI(
    model=os.getenv("DASHSCOPE_CHAT_MODEL"),
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    # Qwen 思考模式不支持 tool_choice=required（结构化输出会用到）
    extra_body={"enable_thinking": False},
)

agent = create_agent(
    model=model,
    system_prompt=(
        "判断用户意图，只能输出 chat / tool / knowledge 之一。\n"
        "- chat: 你好、闲聊、无关医疗办事\n"
        "- tool: 挂号、查医生排班、查费用等需要调业务工具\n"
        "- knowledge: 感冒怎么办、高血压注意事项等知识问答\n"
        "示例：\n"
        "用户：帮我挂明天内科的号 → tool\n"
        "用户：感冒吃什么药 → knowledge\n"
        "用户：你好呀 → chat"
    ),
    response_format=IntentResult,
)


def intent_judgment_node(state: MessagesState) -> MessagesState:
    """
    意图判断节点
    """
    # 读：患者最新要求/问题
    last = state["messages"][-1]
    response = agent.invoke({"messages": [{"role": "user", "content": last.content}]})
    log.info(f"意图判断节点原型结构: {response}")
    # 写：只更新 intent，供后面条件边路由
    return {"intent": response["structured_response"].intent}
