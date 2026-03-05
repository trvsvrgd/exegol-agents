from typing import Any, NotRequired, TypedDict


class GraphState(TypedDict):
    messages: list[Any]
    current_plan: str
    status: str
    evaluation_result: NotRequired[dict[str, Any]]
    evaluator_feedback: NotRequired[str]  # Feedback for Coder retry when evaluation fails
