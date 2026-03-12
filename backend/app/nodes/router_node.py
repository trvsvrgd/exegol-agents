"""Router node: assesses user intent and routes to specialized sub-agents via local Ollama."""
from pathlib import Path

import yaml
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.types import RunnableConfig
from pydantic import BaseModel, Field

from app.logging_config import LOG_TOKEN_USAGE_KEY, extract_usage_from_response
from app.memory import retrieve_relevant
from app.state import GraphState

WORKSPACE_PLAN_PATH = Path(__file__).resolve().parent.parent.parent.parent / "workspace" / "plan.md"
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "agents.yaml"

# Supported routing intents
INTENT_IMPLEMENT = "implement"
INTENT_PLAN_ONLY = "plan_only"
INTENT_EXPLORE = "explore"


class RoutingDecision(BaseModel):
    """Structured output for intent classification and task planning."""

    intent: str = Field(
        description="One of: implement (user wants code changes, file writes, or execution), "
        "plan_only (user wants only a plan or breakdown, no execution), "
        "explore (user wants to read files, understand structure, or browse the codebase without changes)."
    )
    task_description: str = Field(
        description="A clear, actionable task for the target sub-agent. Be specific about files, functions, or behavior."
    )
    rationale: str = Field(
        default="",
        description="Brief reasoning for the intent choice (optional).",
    )


def _load_router_config() -> dict:
    """Load router model config from config/agents.yaml if present."""
    if not CONFIG_PATH.exists():
        return {"model": "qwen2.5-coder", "base_url": "http://localhost:11434"}
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        # Router uses planner config (or dedicated router section if added later)
        router = data.get("router", data.get("planner", {}))
        return {
            "model": router.get("model", "qwen2.5-coder"),
            "base_url": router.get("base_url", "http://localhost:11434"),
        }
    except Exception:
        return {"model": "qwen2.5-coder", "base_url": "http://localhost:11434"}


def _normalize_intent(intent: str) -> str:
    """Normalize intent string to a known routing target."""
    i = (intent or "").strip().lower()
    if i in (INTENT_IMPLEMENT, INTENT_PLAN_ONLY, INTENT_EXPLORE):
        return i
    # Map common synonyms
    if i in ("code", "execute", "build", "implement", "write", "create", "fix", "refactor"):
        return INTENT_IMPLEMENT
    if i in ("plan", "planning", "outline", "breakdown", "design"):
        return INTENT_PLAN_ONLY
    if i in ("explore", "exploration", "read", "browse", "understand", "inspect", "review"):
        return INTENT_EXPLORE
    return INTENT_IMPLEMENT  # Default to implement for ambiguous cases


def router_node(state: GraphState, config: RunnableConfig | None = None) -> dict:
    """
    Assess user intent and produce a task plan.
    Routes to: implement (approval->coder), plan_only (END), or explore (explorer).
    """
    cfg = _load_router_config()
    llm = ChatOllama(
        model=cfg["model"],
        base_url=cfg["base_url"],
        format="json",
    )

    parser = PydanticOutputParser(pydantic_object=RoutingDecision)
    format_instructions = parser.get_format_instructions()

    plan_content = ""
    if WORKSPACE_PLAN_PATH.exists():
        plan_content = WORKSPACE_PLAN_PATH.read_text(encoding="utf-8")

    memory_context = retrieve_relevant(user_text, k=5)

    system = """You are a task router for a coding agent platform. Assess the user's intent and produce a routing decision.

Routing intents:
- implement: User wants code changes, file writes, running commands, tests, or any modification/execution.
- plan_only: User wants only a plan, outline, breakdown, or design—no execution or file changes.
- explore: User wants to read files, understand structure, browse the codebase, or inspect without making changes.

Output ONLY valid JSON matching the schema. No markdown, no extra text.
{format_instructions}

When relevant, consider past architectural decisions and SOPs from memory to inform routing and task planning."""

    user_msg = state["messages"][-1] if state["messages"] else {}
    user_text = (
        user_msg.get("content", str(user_msg))
        if isinstance(user_msg, dict)
        else getattr(user_msg, "content", str(user_msg))
    )

    memory_section = ""
    if memory_context:
        memory_section = f"\nRelevant past decisions/SOPs from memory:\n{memory_context}\n"

    prompt = f"""User request: {user_text}

Existing plan (if any):
{plan_content or "(none)"}
{memory_section}
Output the routing decision as JSON:"""

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
        decision = parser.parse(raw)
        intent = _normalize_intent(decision.intent)
        task = decision.task_description
        rationale = decision.rationale or ""
    except Exception as e:
        intent = INTENT_IMPLEMENT
        task = raw.strip() if raw.strip() else f"Execute user request: {user_text[:200]}"
        rationale = f"[Parse fallback: {e}]"

    planner_content = task
    if rationale:
        planner_content = f"{task}\n\nRationale: {rationale}"

    out: dict = {
        "messages": state["messages"] + [{"role": "router", "content": planner_content}],
        "current_plan": task,
        "routed_intent": intent,
        "status": "routed",
    }
    usage = extract_usage_from_response(response)
    if usage is not None:
        out[LOG_TOKEN_USAGE_KEY] = usage
    return out
