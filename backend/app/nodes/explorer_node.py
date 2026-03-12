"""Explorer node: read-only codebase exploration sub-agent. No file writes or command execution."""
import asyncio
import json

from langchain_community.chat_models import ChatOllama
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import RunnableConfig

from app.logging_config import LOG_TOKEN_USAGE_KEY, extract_usage_from_response
from app.state import GraphState
from app.tools.mcp_client import get_sandbox_mcp_tools

# Tools allowed for read-only exploration (no write_file, run_bash, run_pytest)
READ_ONLY_TOOLS = {"read_file", "list_dir"}


def _get_task_from_state(state: GraphState) -> str:
    """Extract exploration task from state."""
    return state.get("current_plan", "Explore the codebase based on the user request.")


def _merge_usage(acc: dict | None, new: dict | None) -> dict:
    if not new:
        return acc or {}
    out = dict(acc or {})
    for k in ("prompt_eval_count", "eval_count", "total"):
        v = new.get(k)
        if v is not None:
            out[k] = out.get(k, 0) + v
    return out


async def _run_explorer(state: GraphState) -> tuple[str, dict | None]:
    """Run the explorer with read-only MCP tools. Returns (output, token_usage)."""
    task = _get_task_from_state(state)
    messages_list = state.get("messages", [])
    user_text = ""
    for m in reversed(messages_list):
        if m.get("role") == "user":
            user_text = m.get("content", str(m))
            break

    llm = ChatOllama(base_url="http://localhost:11434", model="qwen2.5-coder")
    aggregated_usage: dict | None = None

    async with get_sandbox_mcp_tools() as (session, all_tools):
        # Restrict to read-only tools only
        tools = [t for t in all_tools if t.name in READ_ONLY_TOOLS]
        if not tools:
            tools = all_tools  # Fallback if names differ
        llm_with_tools = llm.bind_tools(tools)

        system = """You are an EXPLORER sub-agent. Your job is to explore and understand the codebase—READ ONLY.

You MUST:
- Use read_file to read file contents
- Use list_dir to browse directories and understand structure

You MUST NOT:
- Use write_file, run_bash, run_pytest, or any tool that modifies files or runs commands
- Make any changes to the codebase

After exploring, summarize what you found for the user: structure, key files, how things connect. Be concise."""

        messages = [
            SystemMessage(content=system),
            HumanMessage(content=f"User request: {user_text}\n\nExploration task: {task}"),
        ]

        max_tool_rounds = 8
        for _ in range(max_tool_rounds):
            response = await llm_with_tools.ainvoke(messages)
            aggregated_usage = _merge_usage(
                aggregated_usage, extract_usage_from_response(response)
            )

            if not isinstance(response, AIMessage):
                return getattr(response, "content", str(response)), aggregated_usage

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                return response.content or "", aggregated_usage

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
                    result = f"Tool {name} not available in explorer mode"

                tool_msg_id = (
                    tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                ) or f"call_{name}"
                messages.append(ToolMessage(content=str(result), tool_call_id=tool_msg_id))

        return (
            response.content if hasattr(response, "content") else "Exploration complete.",
            aggregated_usage,
        )


def explorer_node(state: GraphState, config: RunnableConfig | None = None) -> dict:
    """Read-only exploration of the codebase. Routes here when intent is 'explore'."""
    try:
        output, usage = asyncio.run(_run_explorer(state))
    except Exception as e:
        output = f"[Explorer Error] {e}"
        usage = None

    out: dict = {
        "messages": state["messages"] + [{"role": "explorer", "content": output}],
        "status": "explored",
    }
    if usage:
        out[LOG_TOKEN_USAGE_KEY] = usage
    return out
