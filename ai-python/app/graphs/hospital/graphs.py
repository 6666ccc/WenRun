from app.graphs.hospital.nodes.begin import begin_node
from app.graphs.hospital.nodes.chat import chat_node
from app.graphs.hospital.nodes.final import final_node
from app.graphs.hospital.nodes.knowledge import knowledge_node
from app.graphs.hospital.state import State
from langgraph.graph import END, START, StateGraph

workflow = StateGraph(State)

workflow.add_node("begin_node", begin_node)
workflow.add_node("knowledge_node", knowledge_node)
workflow.add_node("chat_node", chat_node)
workflow.add_node("final_node", final_node)


workflow.add_edge(START, "begin_node")
workflow.add_edge("begin_node", "knowledge_node")
workflow.add_edge("knowledge_node", "chat_node")
workflow.add_edge("chat_node", "final_node")
workflow.add_edge("final_node", END)


graph = workflow.compile()
