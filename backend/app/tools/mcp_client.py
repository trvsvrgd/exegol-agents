"""
MCP client that reads mcp_servers.json, starts MCP servers via stdio, and exposes
tools as LangChain Tool objects.
"""
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _get_project_root() -> Path:
    """Return the exegol-agents project root (parent of backend)."""
    # backend/app/tools/mcp_client.py -> go up 3 levels to backend, 1 more to project
    return Path(__file__).resolve().parent.parent.parent.parent


def _get_config_path() -> Path:
    """Return the path to mcp_servers.json."""
    return _get_project_root() / "config" / "mcp_servers.json"


def _resolve_path_from_project(path_arg: str) -> Path:
    """Resolve a path (e.g. '../workspace') relative to project root to absolute."""
    return (_get_project_root() / path_arg).resolve()


def _load_mcp_config() -> dict[str, Any]:
    """Load mcp_servers.json. Returns {} if missing or invalid."""
    config_path = _get_config_path()
    if not config_path.exists():
        return {}
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _build_server_params(server_config: dict[str, Any]) -> StdioServerParameters:
    """Build StdioServerParameters from server config, resolving paths to absolute."""
    command = server_config.get("command", "npx")
    args = list(server_config.get("args", []))
    env = server_config.get("env")

    # Resolve path args to absolute (workspace, ./dir, ../workspace); leave packages unchanged
    resolved_args = []
    path_like = ("-", "@", "/")  # flags, npm packages, absolute
    for arg in args:
        if (
            isinstance(arg, str)
            and not Path(arg).is_absolute()
            and not any(arg.startswith(p) for p in path_like)
        ):
            try:
                resolved = _resolve_path_from_project(arg)
                resolved_args.append(str(resolved))
                continue
            except (OSError, ValueError):
                pass
        resolved_args.append(arg)

    return StdioServerParameters(
        command=command,
        args=resolved_args,
        env=env,
    )


def _extract_text_from_result(result: Any) -> str:
    """Extract text content from MCP CallToolResult."""
    if result.isError:
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return f"Error: {' '.join(parts) if parts else 'Unknown error'}"
    parts = []
    for block in result.content:
        if hasattr(block, "text") and block.text:
            parts.append(block.text)
    return "\n".join(parts) if parts else ""


@asynccontextmanager
async def get_filesystem_tools():
    """
    Async context manager that connects to the filesystem MCP server and yields
    (session, tools). Session and transport are cleaned up on exit.
    """
    config = _load_mcp_config()
    if "filesystem" not in config:
        raise ValueError("MCP server 'filesystem' not found in config")

    params = _build_server_params(config["filesystem"])
    stdio_ctx = stdio_client(params)

    async with stdio_ctx as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            list_result = await session.list_tools()
            tools = _create_langchain_tools(session, list_result.tools)
            yield session, tools


def _create_langchain_tools(session: ClientSession, mcp_tools: list) -> list[StructuredTool]:
    """Convert MCP tools to LangChain StructuredTool objects with async support."""
    tools = []
    for mcp_tool in mcp_tools:
        name = getattr(mcp_tool, "name", None) or (
            mcp_tool.get("name", "unknown") if isinstance(mcp_tool, dict) else "unknown"
        )
        description = (
            getattr(mcp_tool, "description", None)
            or (mcp_tool.get("description") if isinstance(mcp_tool, dict) else None)
            or f"MCP tool: {name}"
        )
        input_schema = (
            getattr(mcp_tool, "inputSchema", None)
            or (mcp_tool.get("inputSchema") if isinstance(mcp_tool, dict) else None)
        ) or {"type": "object", "properties": {}}

        def _make_tool_funcs(tool_name: str):
            async def _async_call(**kwargs: Any) -> str:
                result = await session.call_tool(tool_name, kwargs)
                return _extract_text_from_result(result)

            def _sync_call(**kwargs: Any) -> str:
                return asyncio.run(_async_call(**kwargs))

            return _async_call, _sync_call

        coro, sync_func = _make_tool_funcs(name)
        tools.append(
            StructuredTool.from_function(
                func=sync_func,
                coroutine=coro,
                name=name,
                description=description or f"Tool: {name}",
                args_schema=input_schema,
                infer_schema=False,
            )
        )
    return tools
