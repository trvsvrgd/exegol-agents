"""Coder node: ChatOllama with MCP filesystem tools for code execution."""
import asyncio
import json

from langchain_community.chat_models import ChatOllama
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.state import GraphState
from app.tools.mcp_client import get_filesystem_tools


def _get_task_and_context(state: GraphState) -> tuple[str, str]:
    """Extract task and user context from state. Includes evaluator feedback for retries."""
    task = state.get("current_plan", "No task")
    evaluator_feedback = state.get("evaluator_feedback", "")
    if evaluator_feedback:
        task = f"{task}\n\n[Evaluator feedback - address this]: {evaluator_feedback}"
    messages = state.get("messages", [])
    user_text = ""
    if messages:
        last_user = next(
            (m for m in reversed(messages) if m.get("role") == "user"),
            None,
        )
        if last_user:
            user_text = last_user.get("content", str(last_user))
    return task, user_text


async def _run_coder_with_tools(state: GraphState) -> str:
    """Run the coder with MCP filesystem tools, handling tool calls."""
    task, user_text = _get_task_and_context(state)
    llm = ChatOllama(base_url="http://localhost:11434", model="qwen2.5-coder")

    async with get_filesystem_tools() as (session, tools):
        llm_with_tools = llm.bind_tools(tools)

        system = """You are a coder with access to the local filesystem. You can read files, write files, and list directories.
Execute the task you are given. Use the filesystem tools when you need to read or write code. Be concise."""

        messages = [
            SystemMessage(content=system),
            HumanMessage(
                content=f"User request: {user_text}\n\nTask to execute: {task}"
            ),
        ]

        max_tool_rounds = 10
        for _ in range(max_tool_rounds):
            response = await llm_with_tools.ainvoke(messages)

            if not isinstance(response, AIMessage):
                return getattr(response, "content", str(response))

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                return response.content or ""

            messages.append(response)

            for tc in tool_calls:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args else {}
                    except json.JSONDecodeError:
                        args = {}

                tool = next((t for t in tools if t.name == name), None)
                if tool:
                    try:
                        result = await tool.ainvoke(args)
                    except Exception as e:
                        result = f"Error: {e}"
                else:
                    result = f"Tool {name} not found"

                tool_msg_id = (
                    tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                ) or f"call_{name}"
                messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_msg_id)
                )

        return response.content if hasattr(response, "content") else "Max tool rounds reached"


def coder_node(state: GraphState) -> dict:
    """Uses ChatOllama with MCP filesystem tools. Handles tool calls (read_file, etc.)."""
    try:
        output = asyncio.run(_run_coder_with_tools(state))
    except Exception as e:
        output = f"[Error] {e}"

    return {
        "messages": state["messages"] + [{"role": "coder", "content": output}],
        "status": "completed",
    }
