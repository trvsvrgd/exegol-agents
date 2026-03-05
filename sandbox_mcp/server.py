"""
Sandbox MCP Server: Runs inside a Docker container.
Provides filesystem, bash, and pytest tools scoped to /workspace.
All operations are restricted to the project workspace to prevent breakout.
"""
import logging
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Workspace root - all paths must resolve within this directory
WORKSPACE = Path("/workspace")

# Safeguards
BASH_TIMEOUT_SEC = 60
PYTEST_TIMEOUT_SEC = 120

# Log to stderr only (stdout is used for MCP JSON-RPC)
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

mcp = FastMCP("exegol-sandbox")


def _resolve_safe(path_str: str) -> Path | None:
    """
    Resolve a path relative to workspace. Returns None if path escapes workspace.
    """
    if not path_str:
        return None
    try:
        # Support paths relative to workspace (e.g. "foo/bar", "./test.py")
        p = Path(path_str)
        if not p.is_absolute():
            p = WORKSPACE / p
        resolved = p.resolve()
        if not str(resolved).startswith(str(WORKSPACE.resolve())):
            return None
        return resolved
    except (OSError, ValueError):
        return None


@mcp.tool()
def read_file(path: str) -> str:
    """Read the contents of a file in the workspace.

    Args:
        path: Path relative to workspace (e.g. 'test.py', 'src/main.py')
    """
    resolved = _resolve_safe(path)
    if resolved is None:
        return f"Error: Invalid or escaped path: {path}. Path must be within workspace."
    if not resolved.exists():
        return f"Error: File not found: {path}"
    if not resolved.is_file():
        return f"Error: Not a file: {path}"
    try:
        return resolved.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"Error reading file: {e}"


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file in the workspace. Creates parent directories if needed.

    Args:
        path: Path relative to workspace (e.g. 'test.py', 'src/main.py')
        content: Content to write
    """
    resolved = _resolve_safe(path)
    if resolved is None:
        return f"Error: Invalid or escaped path: {path}. Path must be within workspace."
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return f"Wrote {path} ({len(content)} bytes)"
    except OSError as e:
        return f"Error writing file: {e}"


@mcp.tool()
def list_dir(path: str = ".") -> str:
    """List files and directories in a workspace path.

    Args:
        path: Path relative to workspace (default: current directory)
    """
    resolved = _resolve_safe(path)
    if resolved is None:
        return f"Error: Invalid or escaped path: {path}. Path must be within workspace."
    if not resolved.exists():
        return f"Error: Path not found: {path}"
    if not resolved.is_dir():
        return f"Error: Not a directory: {path}"
    try:
        entries = sorted(resolved.iterdir())
        lines = []
        for e in entries:
            typ = "d" if e.is_dir() else "f"
            lines.append(f"{typ} {e.name}")
        return "\n".join(lines) if lines else "(empty)"
    except OSError as e:
        return f"Error listing directory: {e}"


def _run_subprocess(cmd: list[str], timeout: int, cwd: Path) -> tuple[int, str, str]:
    """Run a command; returns (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


@mcp.tool()
def run_bash(command: str, timeout_sec: int = BASH_TIMEOUT_SEC) -> str:
    """Run a bash command in the workspace directory.
    Commands are always executed with the workspace as the working directory.
    Use for installing dependencies, running scripts, or other terminal operations.

    Args:
        command: Shell command to run (e.g. 'pip install -r requirements.txt')
        timeout_sec: Max execution time in seconds (default 60, max 120)
    """
    if timeout_sec > 120:
        timeout_sec = 120
    if timeout_sec < 1:
        timeout_sec = 1
    # Run in workspace; use bash -c for shell features
    cmd = ["bash", "-c", command]
    exit_code, stdout, stderr = _run_subprocess(cmd, timeout_sec, WORKSPACE)
    out_parts = []
    if stdout:
        out_parts.append(stdout)
    if stderr:
        out_parts.append(f"stderr:\n{stderr}")
    out_parts.append(f"\n[exit_code={exit_code}]")
    return "\n".join(out_parts)


@mcp.tool()
def run_pytest(
    path: str = ".",
    extra_args: str = "-v",
    timeout_sec: int = PYTEST_TIMEOUT_SEC,
) -> str:
    """Run pytest in the workspace. Use to verify code changes.

    Args:
        path: Path to test (file, dir, or '.' for whole workspace)
        extra_args: Extra pytest args (default: '-v')
        timeout_sec: Max execution time in seconds (default 120, max 180)
    """
    if timeout_sec > 180:
        timeout_sec = 180
    if timeout_sec < 10:
        timeout_sec = 10
    resolved = _resolve_safe(path) if path and path != "." else WORKSPACE
    if resolved is None:
        return f"Error: Invalid path: {path}"
    target = str(resolved) if path and path != "." else "."
    args = ["python", "-m", "pytest", target]
    if extra_args:
        args.extend(extra_args.split())
    exit_code, stdout, stderr = _run_subprocess(args, timeout_sec, WORKSPACE)
    out_parts = []
    if stdout:
        out_parts.append(stdout)
    if stderr:
        out_parts.append(f"stderr:\n{stderr}")
    out_parts.append(f"\n[exit_code={exit_code}]")
    return "\n".join(out_parts)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
