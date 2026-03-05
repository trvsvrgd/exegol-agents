"""Coder node: ChatOllama with MCP filesystem tools for code execution."""
import asyncio
import json

from langchain_community.chat_models import ChatOllama
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import RunnableConfig

from app.logging_config import LOG_TOKEN_USAGE_KEY, extract_usage_from_response
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


def _merge_usage(acc: dict | None, new: dict | None) -> dict:
    """Merge token usage from a new response into accumulated totals."""
    if not new:
        return acc or {}
    out = dict(acc or {})
    for k in ("prompt_eval_count", "eval_count", "total"):
        v = new.get(k)
        if v is not None:
            out[k] = out.get(k, 0) + v
    return out


def _format_tool_results(entries: list[tuple[str, dict, str]]) -> str:
    """Format tool call entries for evaluator context. Truncate long content."""
    lines = []
    for name, args, result in entries:
        args_str = json.dumps(args, default=str)[:200]
        result_str = str(result)[:500] if result else "(empty)"
        if len(str(result)) > 500:
            result_str += "..."
        lines.append(f"- {name}({args_str}): {result_str}")
    return "\n".join(lines) if lines else ""


async def _run_coder_with_tools(state: GraphState) -> tuple[str, dict | None, list[tuple[str, dict, str]]]:
    """Run the coder with MCP filesystem tools. Returns (output, aggregated_usage, tool_results)."""
    task, user_text = _get_task_and_context(state)
    llm = ChatOllama(base_url="http://localhost:11434", model="qwen2.5-coder")
    aggregated_usage: dict | None = None
    tool_entries: list[tuple[str, dict, str]] = []

    async with get_filesystem_tools() as (session, tools):
        llm_with_tools = llm.bind_tools(tools)

        system = """You are a coder with access to the local filesystem. You can read files, write files, and list directories.
Execute the task you are given. Use the filesystem tools when you need to read or write code.
After using tools, always summarize what you did: list files created or modified with their key contents (or snippets), so the evaluator can verify your work. Be concise."""

        messages = [
            SystemMessage(content=system),
            HumanMessage(
                content=f"User request: {user_text}\n\nTask to execute: {task}"
            ),
        ]

        max_tool_rounds = 10
        for _ in range(max_tool_rounds):
            response = await llm_with_tools.ainvoke(messages)
            aggregated_usage = _merge_usage(
                aggregated_usage, extract_usage_from_response(response)
            )

            if not isinstance(response, AIMessage):
                return getattr(response, "content", str(response)), aggregated_usage, tool_entries

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                return response.content or "", aggregated_usage, tool_entries

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

                tool_entries.append((name, args, str(result)))

                tool_msg_id = (
                    tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                ) or f"call_{name}"
                messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_msg_id)
                )

        return (
            response.content if hasattr(response, "content") else "Max tool rounds reached",
            aggregated_usage,
            tool_entries,
        )


def coder_node(state: GraphState, config: RunnableConfig | None = None) -> dict:
    """Uses ChatOllama with MCP filesystem tools. Handles tool calls (read_file, etc.)."""
    try:
        output, usage, tool_entries = asyncio.run(_run_coder_with_tools(state))
    except Exception as e:
        output = f"[Error] {e}"
        usage = None
        tool_entries = []

    out: dict = {
        "messages": state["messages"] + [{"role": "coder", "content": output}],
        "status": "completed",
    }
    if usage:
        out[LOG_TOKEN_USAGE_KEY] = usage
    if tool_entries:
        out["coder_tool_results"] = _format_tool_results(tool_entries)
    return out
