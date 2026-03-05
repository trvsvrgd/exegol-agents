"""Rejected node: Terminal state when human rejects the plan."""

from langgraph.types import RunnableConfig

from app.state import GraphState


def rejected_node(state: GraphState, config: RunnableConfig | None = None) -> dict:
    """Mark execution as rejected; graph proceeds to END."""
    return {
        "messages": state.get("messages", [])
        + [{"role": "system", "content": "Plan rejected by user."}],
        "status": "rejected",
    }
