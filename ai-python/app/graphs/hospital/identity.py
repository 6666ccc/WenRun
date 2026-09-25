"""会话隔离用的标识生成：同名会话在不同登录用户之间不能共用检查点。"""


def thread_id_for(user_id: int, conversation_id: str) -> str:
    """把已验证用户 ID 与会话 ID 拼成 LangGraph 的独立线程键。"""

    return f"user:{user_id}:conversation:{conversation_id}"
