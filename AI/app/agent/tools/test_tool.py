from langchain.tools import tool

@tool
def test_tool(name: str) -> str:
    """测试工具"""
    return f"Hello, {name}!"