"""Approval node: Human-in-the-loop interrupt before Coder/Executor runs."""

from langgraph.types import Command, interrupt

from app.state import GraphState


def approval_node(state: GraphState) -> Command:
    """
    Pause execution and wait for human approval before the Coder runs.
    Resume value should be {"decision": "approve"|"edit"|"reject", "edited_plan": "..." (if edit)}.
    """
    payload = {
        "type": "approval_required",
        "message": "Review the plan before the Coder executes. Approve, edit, or reject.",
        "plan": state.get("current_plan", ""),
        "messages": state.get("messages", []),
    }

    decision_data = interrupt(payload)

    # Normalize: accept "approve" string or {"decision": "approve", "edited_plan": "..."}
    if isinstance(decision_data, str):
        decision = decision_data.lower()
        edited_plan = None
    else:
        decision_data = decision_data or {}
        decision = (decision_data.get("decision") or "").lower()
        edited_plan = decision_data.get("edited_plan")

    if decision == "reject":
        return Command(update={"status": "rejected"}, goto="rejected")

    if decision == "edit" and edited_plan:
        return Command(
            update={"current_plan": edited_plan, "status": "approved_after_edit"},
            goto="coder",
        )

    # "approve" or fallback
    return Command(update={"status": "approved"}, goto="coder")
