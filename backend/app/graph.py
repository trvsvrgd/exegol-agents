from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.state import GraphState
from app.nodes.planner_node import planner_node
from app.nodes.coder_node import coder_node
from app.nodes.evaluator_node import evaluator_node


def _route_after_evaluator(state: GraphState) -> str:
    """Route to END if tests passed, else back to planner to fix."""
    result = state.get("evaluation_result") or {}
    exit_code = result.get("exit_code", -1)
    return "end" if exit_code == 0 else "planner"


def _build_graph():
    """Build and compile the LangGraph workflow."""
    graph_builder = StateGraph(GraphState)
    graph_builder.add_node("planner", planner_node)
    graph_builder.add_node("coder", coder_node)
    graph_builder.add_node("evaluator", evaluator_node)
    graph_builder.add_edge(START, "planner")
    graph_builder.add_edge("planner", "coder")
    graph_builder.add_edge("coder", "evaluator")
    graph_builder.add_conditional_edges(
        "evaluator",
        _route_after_evaluator,
        {"end": END, "planner": "planner"},
    )
    return graph_builder.compile()


def build_and_stream_graph(prompt: str):
    """Yield (node_name, state) as the graph runs for status polling."""
    graph = _build_graph()
    initial_state: GraphState = {
        "messages": [{"role": "user", "content": prompt}],
        "current_plan": "",
        "status": "started",
    }
    # Merge state as we stream updates
    merged: dict = dict(initial_state)
    for chunk in graph.stream(initial_state, stream_mode="updates"):
        for node_name, update in chunk.items():
            merged.update(update)
            yield node_name, merged


def run_graph(prompt: str) -> dict:
    """Build and run the LangGraph workflow: START -> Planner -> Coder -> Evaluator -> [END | Planner]."""
    graph = _build_graph()
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
        "evaluation_result": result.get("evaluation_result"),
    }
