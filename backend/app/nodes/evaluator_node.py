"""Evaluator node: runs pytest in Docker and formats results for the state."""
from app.state import GraphState
from app.tools.docker_eval import run_docker_pytest


def evaluator_node(state: GraphState) -> dict:
    """
    Run pytest in a Docker container and append formatted results to state.

    Returns updated state with evaluation_result and a new evaluator message.
    """
    result = run_docker_pytest()
    exit_code = result.get("exit_code", -1)
    logs = result.get("logs", "")
    error = result.get("error")

    if error:
        message = f"[Evaluator] Docker evaluation error: {error}\n\nLogs (if any):\n{logs}"
    elif exit_code == 0:
        message = f"[Evaluator] All tests passed (exit code 0).\n\n```\n{logs}\n```"
    else:
        message = (
            f"[Evaluator] Tests failed (exit code {exit_code}). "
            "Review the output below for the Planner to fix.\n\n```\n{logs}\n```"
        )

    return {
        "messages": state["messages"] + [{"role": "evaluator", "content": message}],
        "evaluation_result": result,
        "status": "passed" if exit_code == 0 else "failed",
    }
