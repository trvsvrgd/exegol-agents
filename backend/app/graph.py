"""LangGraph workflow with Human-in-the-Loop approval before Coder."""

import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, END, START
from langgraph.types import Command

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.logging_config import (
    LOG_TOKEN_USAGE_KEY,
    LOG_TOOL_CALLS_KEY,
    log_node_end,
    log_node_start,
)
from app.state import GraphState
from app.nodes.router_node import router_node, INTENT_IMPLEMENT, INTENT_PLAN_ONLY, INTENT_EXPLORE
from app.nodes.approval_node import approval_node
from app.nodes.coder_node import coder_node
from app.nodes.rejected_node import rejected_node
from app.nodes.evaluator_node import evaluator_node
from app.nodes.explorer_node import explorer_node

# Module-level checkpointer for state persistence across invoke and resume
_checkpointer = InMemorySaver()

MAX_CODER_RETRIES = 3

def _wrap_node(node_name: str, node_fn):
    """Wrap a node to log start, end, duration, and token usage (if present)."""

    def wrapped(state: GraphState, config=None):
        cfg = config or {}
        thread_id = cfg.get("configurable", {}).get("thread_id", "-")
        log_node_start(node_name, thread_id)
        t0 = time.perf_counter()
        try:
            result = node_fn(state, config) if _accepts_config(node_fn) else node_fn(state)
        except Exception:
            log_node_end(node_name, thread_id, time.perf_counter() - t0, None)
            raise
        token_usage = None
        tool_calls = None
        if isinstance(result, dict):
            if LOG_TOKEN_USAGE_KEY in result:
                token_usage = result.pop(LOG_TOKEN_USAGE_KEY)
            if LOG_TOOL_CALLS_KEY in result:
                tool_calls = result.pop(LOG_TOOL_CALLS_KEY)
            if not result:
                result = {}
        log_node_end(node_name, thread_id, time.perf_counter() - t0, token_usage, tool_calls)
        return result

    return wrapped


def _accepts_config(fn) -> bool:
    """Check if the node function accepts a config argument."""
    import inspect
    sig = inspect.signature(fn)
    params = list(sig.parameters)
    return len(params) >= 2


def _route_after_router(state: GraphState) -> str:
    """Route to specialized sub-agents based on assessed intent."""
    intent = state.get("routed_intent", INTENT_IMPLEMENT)
    if intent == INTENT_PLAN_ONLY:
        return "end"
    if intent == INTENT_EXPLORE:
        return "explorer"
    return "approval"


def _route_after_evaluator(state: GraphState) -> str:
    """Route to END if evaluation passed, else back to Coder with feedback for retry."""
    result = state.get("evaluation_result") or {}
    success = result.get("success", False)
    if success:
        return "end"
    retry_count = state.get("retry_count", 0)
    if retry_count >= MAX_CODER_RETRIES:
        return "end"  # Give up after max retries
    return "coder"


def _build_graph():
    """Build and compile the LangGraph workflow with dynamic routing and HITL before Coder."""
    graph_builder = StateGraph(GraphState)
    graph_builder.add_node("router", _wrap_node("router", router_node))
    graph_builder.add_node("approval", _wrap_node("approval", approval_node))
    graph_builder.add_node("coder", _wrap_node("coder", coder_node))
    graph_builder.add_node("rejected", _wrap_node("rejected", rejected_node))
    graph_builder.add_node("evaluator", _wrap_node("evaluator", evaluator_node))
    graph_builder.add_node("explorer", _wrap_node("explorer", explorer_node))

    graph_builder.add_edge(START, "router")
    graph_builder.add_conditional_edges(
        "router",
        _route_after_router,
        {
            "end": END,
            "approval": "approval",
            "explorer": "explorer",
        },
    )
    # approval -> coder or approval -> rejected via Command(goto=...) in approval_node
    graph_builder.add_edge("rejected", END)
    graph_builder.add_edge("explorer", END)
    graph_builder.add_edge("coder", "evaluator")
    graph_builder.add_conditional_edges(
        "evaluator",
        _route_after_evaluator,
        {"end": END, "coder": "coder"},
    )
    return graph_builder.compile(checkpointer=_checkpointer)


def build_and_stream_graph(prompt: str, thread_id: str | None = None):
    """
    Yield (node_name, state) as the graph runs.
    When interrupt hits, yields ("__interrupt__", {state, interrupt_info}) and stops.
    """
    thread_id = thread_id or str(uuid.uuid4())
    graph = _build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    initial_state: GraphState = {
        "messages": [{"role": "user", "content": prompt}],
        "current_plan": "",
        "status": "started",
        "retry_count": 0,
    }
    merged: dict = dict(initial_state)

    for chunk in graph.stream(initial_state, config=config, stream_mode="updates"):
        if "__interrupt__" in chunk:
            interrupt_data = chunk["__interrupt__"]
            yield "__interrupt__", {
                "merged": merged,
                "interrupt": [
                    {"value": getattr(i, "value", i), "id": getattr(i, "id", None)}
                    for i in (interrupt_data if isinstance(interrupt_data, (list, tuple)) else [interrupt_data])
                ],
                "thread_id": thread_id,
            }
            return

        for node_name, update in chunk.items():
            merged.update(update)
            yield node_name, merged


def run_graph(prompt: str, thread_id: str | None = None) -> dict:
    """Run the graph: START -> Router -> [Approval->Coder->Evaluator | Explorer | END (plan_only)]."""
    thread_id = thread_id or str(uuid.uuid4())
    graph = _build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    initial_state: GraphState = {
        "messages": [{"role": "user", "content": prompt}],
        "current_plan": "",
        "status": "started",
        "retry_count": 0,
    }
    result = graph.invoke(initial_state, config=config)
    return {
        "messages": result["messages"],
        "current_plan": result["current_plan"],
        "status": result["status"],
        "routed_intent": result.get("routed_intent"),
        "evaluation_result": result.get("evaluation_result"),
    }


def resume_graph(
    thread_id: str,
    decision: str,
    edited_plan: str | None = None,
) -> dict | None:
    """
    Resume the graph after human approval.
    Returns result dict, or None if thread_id not found / graph not interrupted.
    """
    graph = _build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    resume_value = {"decision": decision}
    if decision == "edit" and edited_plan:
        resume_value["edited_plan"] = edited_plan

    result = graph.invoke(Command(resume=resume_value), config=config)

    if "__interrupt__" in result:
        return {
            "status": "awaiting_approval",
            "__interrupt__": result["__interrupt__"],
            "messages": result.get("messages", []),
            "current_plan": result.get("current_plan", ""),
            "evaluation_result": result.get("evaluation_result"),
        }

    return {
        "messages": result["messages"],
        "current_plan": result["current_plan"],
        "status": result["status"],
        "evaluation_result": result.get("evaluation_result"),
    }


def stream_resume_graph(thread_id: str, decision: str, edited_plan: str | None = None):
    """
    Resume the graph and stream updates.
    Yields (node_name, state) like build_and_stream_graph.
    On another interrupt, yields ("__interrupt__", {...}).
    """
    graph = _build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    resume_value = {"decision": decision}
    if decision == "edit" and edited_plan:
        resume_value["edited_plan"] = edited_plan

    # Start with current checkpoint state
    try:
        snapshot = graph.get_state(config)
        merged = dict(snapshot.values) if snapshot.values else {}
    except Exception:
        merged = {}
    for chunk in graph.stream(
        Command(resume=resume_value), config=config, stream_mode="updates"
    ):
        if "__interrupt__" in chunk:
            interrupt_data = chunk["__interrupt__"]
            yield "__interrupt__", {
                "merged": merged,
                "interrupt": [
                    {"value": getattr(i, "value", i), "id": getattr(i, "id", None)}
                    for i in (interrupt_data if isinstance(interrupt_data, (list, tuple)) else [interrupt_data])
                ],
                "thread_id": thread_id,
            }
            return

        for node_name, update in chunk.items():
            merged.update(update)
            yield node_name, merged
