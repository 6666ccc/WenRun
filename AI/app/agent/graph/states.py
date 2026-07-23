
from langgraph.graph import MessagesState
from typing import Literal

class State(MessagesState):
  user_id: str
  intent: Literal["chat", "tool", "knowledge"] | None = None
