"""Planner node: local Ollama for task decomposition with structured JSON output."""
from pathlib import Path

import yaml
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from app.state import GraphState

WORKSPACE_PLAN_PATH = Path(__file__).resolve().parent.parent.parent.parent / "workspace" / "plan.md"
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "agents.yaml"


class TaskPlan(BaseModel):
    """Structured task plan schema for reliable JSON output from local models."""

    task_description: str = Field(
        description="A clear, actionable task for the coder. One or two sentences. Be specific about files, functions, or behavior to implement or change."
    )
    rationale: str = Field(
        default="",
        description="Brief reasoning for this task (optional, can be empty string).",
    )


def _load_planner_config() -> dict:
    """Load planner model config from config/agents.yaml if present."""
    if not CONFIG_PATH.exists():
        return {"model": "qwen2.5-coder", "base_url": "http://localhost:11434"}
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        planner = data.get("planner", {})
        return {
            "model": planner.get("model", "qwen2.5-coder"),
            "base_url": planner.get("base_url", "http://localhost:11434"),
        }
    except Exception:
        return {"model": "qwen2.5-coder", "base_url": "http://localhost:11434"}


def planner_node(state: GraphState) -> dict:
    """Reads user message and plan.md, outputs a structured task for the coder via local Ollama."""
    config = _load_planner_config()
    llm = ChatOllama(
        model=config["model"],
        base_url=config["base_url"],
        format="json",
    )

    parser = PydanticOutputParser(pydantic_object=TaskPlan)
    format_instructions = parser.get_format_instructions()

    plan_content = ""
    if WORKSPACE_PLAN_PATH.exists():
        plan_content = WORKSPACE_PLAN_PATH.read_text(encoding="utf-8")

    system = """You are a task planner for a coding agent. Given the user's message and any existing project plan, output a structured task for a coder.

Rules:
- Output ONLY valid JSON matching the schema below. No markdown, no extra text.
- task_description: One clear, actionable task. Be specific (files, functions, behavior).
- rationale: Optional brief reasoning (can be empty string).

{format_instructions}"""

    user_msg = state["messages"][-1] if state["messages"] else {}
    user_text = (
        user_msg.get("content", str(user_msg))
        if isinstance(user_msg, dict)
        else getattr(user_msg, "content", str(user_msg))
    )

    prompt = f"""User request: {user_text}

Existing plan (if any):
{plan_content or "(none)"}

Output the task plan as JSON:"""

    messages = [
        SystemMessage(content=system.format(format_instructions=format_instructions)),
        HumanMessage(content=prompt),
    ]

    raw = ""
    try:
        response = llm.invoke(messages)
        raw = response.content if hasattr(response, "content") else str(response)
        # Handle markdown code blocks if the model wraps JSON
        if "```" in raw:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                raw = raw[start:end]
        plan = parser.parse(raw)
        task = plan.task_description
        planner_content = task
        if plan.rationale:
            planner_content = f"{task}\n\nRationale: {plan.rationale}"
    except Exception as e:
        # Fallback: use raw output or minimal task
        task = raw.strip() if raw.strip() else f"Execute user request: {user_text[:200]}"
        planner_content = f"{task}\n\n[Parse fallback: {e}]"

    return {
        "messages": state["messages"] + [{"role": "planner", "content": planner_content}],
        "current_plan": task,
        "status": "planned",
    }
