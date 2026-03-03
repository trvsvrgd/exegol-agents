from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from app.state import GraphState

WORKSPACE_PLAN_PATH = Path(__file__).resolve().parent.parent.parent.parent / "workspace" / "plan.md"


def planner_node(state: GraphState) -> dict:
    """Reads user message and plan.md, outputs a task for the coder."""
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
    plan_content = ""
    if WORKSPACE_PLAN_PATH.exists():
        plan_content = WORKSPACE_PLAN_PATH.read_text(encoding="utf-8")

    system = """You are a task planner. Given the user's message and any existing project plan, output a clear, actionable task for a coder. Be concise. Output only the task description."""

    user_msg = state["messages"][-1] if state["messages"] else {}
    user_text = (
        user_msg.get("content", str(user_msg))
        if isinstance(user_msg, dict)
        else getattr(user_msg, "content", str(user_msg))
    )

    prompt = f"User: {user_text}\n\nExisting plan (if any):\n{plan_content}\n\nTask for coder:"
    chain = llm | StrOutputParser()
    task = chain.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])

    return {
        "messages": state["messages"] + [{"role": "planner", "content": task}],
        "current_plan": task,
        "status": "planned",
    }
