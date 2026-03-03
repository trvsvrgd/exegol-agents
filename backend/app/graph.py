from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.state import GraphState
from app.nodes.planner_node import planner_node
from app.nodes.coder_node import coder_node


def run_graph(prompt: str) -> dict:
    """Build and run the LangGraph workflow: START -> Planner -> Coder -> END."""
    graph_builder = StateGraph(GraphState)

    graph_builder.add_node("planner", planner_node)
    graph_builder.add_node("coder", coder_node)

    graph_builder.add_edge(START, "planner")
    graph_builder.add_edge("planner", "coder")
    graph_builder.add_edge("coder", END)

    graph = graph_builder.compile()

    initial_state: GraphState = {
        "messages": [{"role": "user", "content": prompt}],
        "current_plan": "",
        "status": "started",
    }

    result = graph.invoke(initial_state)
    return {
        "messages": result["messages"],
        "current_plan": result["current_plan"],
        "status": result["status"],
    }
