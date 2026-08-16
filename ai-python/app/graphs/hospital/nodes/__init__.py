from langchain_core.messages import AIMessage

VALID_INTENTS = frozenset({"chat", "hospital", "medical"})


def invoke_reply_agent(agent, state) -> str:
    messages = state.get("messages", [])
    result = agent.invoke({"messages": messages})
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if result.get("messages"):
            last = result["messages"][-1]
            if isinstance(last, dict):
                return str(last.get("content", ""))
            return str(getattr(last, "content", last))
        if "content" in result:
            return str(result["content"])
    content = getattr(result, "content", None)
    if content is not None:
        return str(content)
    return str(result)


def ai_message(content: str) -> AIMessage:
    return AIMessage(content=content)
