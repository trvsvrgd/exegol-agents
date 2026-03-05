"""Evaluator node: LLM-based review of Coder output against user prompt and approved plan."""

from pathlib import Path

import yaml
from langchain_community.chat_models import ChatOllama
from langgraph.types import RunnableConfig

from app.logging_config import LOG_TOKEN_USAGE_KEY, extract_usage_from_response
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from app.state import GraphState

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "agents.yaml"


class EvaluationResult(BaseModel):
    """Structured evaluation output from the LLM."""

    success: bool = Field(description="True if the Coder's output satisfies the user request and plan.")
    feedback: str = Field(
        description="If success is false, actionable feedback for the Coder to improve. If success is true, brief confirmation or empty string."
    )


def _load_evaluator_config() -> dict:
    """Load evaluator model config from config/agents.yaml if present."""
    if not CONFIG_PATH.exists():
        return {"model": "qwen2.5-coder", "base_url": "http://localhost:11434"}
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        evaluator = data.get("evaluator", {})
        return {
            "model": evaluator.get("model", "qwen2.5-coder"),
            "base_url": evaluator.get("base_url", "http://localhost:11434"),
        }
    except Exception:
        return {"model": "qwen2.5-coder", "base_url": "http://localhost:11434"}


def _get_user_prompt(state: GraphState) -> str:
    """Extract original user prompt from messages."""
    messages = state.get("messages", [])
    for m in reversed(messages):
        if m.get("role") == "user":
            return m.get("content", str(m))
    return ""


def _get_coder_output(state: GraphState) -> str:
    """Extract most recent Coder output from messages."""
    messages = state.get("messages", [])
    for m in reversed(messages):
        if m.get("role") == "coder":
            return m.get("content", str(m))
    return ""


def evaluator_node(state: GraphState, config: RunnableConfig | None = None) -> dict:
    """
    Review Coder output against the original user prompt and approved plan using local Ollama.
    Returns structured evaluation with success flag and feedback string.
    """
    config = _load_evaluator_config()
    llm = ChatOllama(
        model=config["model"],
        base_url=config["base_url"],
        format="json",
    )

    parser = PydanticOutputParser(pydantic_object=EvaluationResult)
    format_instructions = parser.get_format_instructions()

    user_prompt = _get_user_prompt(state)
    approved_plan = state.get("current_plan", "")
    coder_output = _get_coder_output(state)

    system = """You are an evaluator for a coding agent. Review the Coder's output against the original user request and the approved plan.

Rules:
- success: true only if the Coder fully addressed the user's request and followed the plan. Be strict but fair.
- feedback: If success is false, give specific, actionable feedback (what was wrong, what to fix). If success is true, a brief confirmation is enough (or empty string).
- Output ONLY valid JSON matching the schema. No markdown, no extra text.

{format_instructions}"""

    prompt = f"""User request: {user_prompt}

Approved plan: {approved_plan or "(none)"}

Coder output:
{coder_output}

Evaluate and output JSON:"""

    messages = [
        SystemMessage(content=system.format(format_instructions=format_instructions)),
        HumanMessage(content=prompt),
    ]

    raw = ""
    response = None
    try:
        response = llm.invoke(messages)
        raw = response.content if hasattr(response, "content") else str(response)
        if "```" in raw:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                raw = raw[start:end]
        evaluation = parser.parse(raw)
    except Exception as e:
        evaluation = EvaluationResult(success=False, feedback=f"Evaluation parse error: {e}")

    result = {"success": evaluation.success, "feedback": evaluation.feedback}
    message = (
        f"[Evaluator] Task {'passed' if evaluation.success else 'failed'}.\n\n{evaluation.feedback}"
    )

    update: dict = {
        "messages": state["messages"] + [{"role": "evaluator", "content": message}],
        "evaluation_result": result,
        "status": "passed" if evaluation.success else "failed",
    }
    if not evaluation.success:
        update["evaluator_feedback"] = evaluation.feedback

    usage = extract_usage_from_response(response)
    if usage is not None:
        update[LOG_TOKEN_USAGE_KEY] = usage
    return update
