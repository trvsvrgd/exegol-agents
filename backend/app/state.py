from typing import Any, TypedDict


class GraphState(TypedDict):
    messages: list[Any]
    current_plan: str
    status: str
