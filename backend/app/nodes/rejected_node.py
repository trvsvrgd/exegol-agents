"""Rejected node: Terminal state when human rejects the plan."""

from app.state import GraphState


def rejected_node(state: GraphState) -> dict:
    """Mark execution as rejected; graph proceeds to END."""
    return {
        "messages": state.get("messages", [])
        + [{"role": "system", "content": "Plan rejected by user."}],
        "status": "rejected",
    }
