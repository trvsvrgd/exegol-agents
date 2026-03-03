"""
Secure evaluation loop using Docker to run pytest on agent-written code.
"""
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _get_workspace_path() -> Path:
    """Return the absolute path to the workspace directory (project_root/workspace)."""
    return Path(__file__).resolve().parent.parent.parent.parent / "workspace"


def run_docker_pytest() -> dict[str, Any]:
    """
    Run pytest inside a lightweight python:3.11-slim container.

    Mounts the local workspace directory at /workspace, sets the working directory
    to /workspace, runs pytest, and returns the exit code and combined logs.

    Returns:
        dict with keys: exit_code (int), logs (str), error (str | None if no error).
    """
    try:
        import docker
    except ImportError as e:
        logger.error("Docker SDK not installed: %s", e)
        return {
            "exit_code": -1,
            "logs": "",
            "error": f"Docker SDK not installed: {e}",
        }

    workspace = _get_workspace_path()
    if not workspace.exists():
        return {
            "exit_code": -1,
            "logs": "",
            "error": f"Workspace directory does not exist: {workspace}",
        }

    container = None
    try:
        client = docker.from_env()
        client.ping()
    except docker.errors.DockerException as e:
        logger.error("Docker daemon not available: %s", e)
        return {
            "exit_code": -1,
            "logs": "",
            "error": f"Docker daemon not running or not accessible: {e}",
        }
    except Exception as e:
        logger.exception("Unexpected error connecting to Docker: %s", e)
        return {
            "exit_code": -1,
            "logs": "",
            "error": str(e),
        }

    try:
        container = client.containers.run(
            image="python:3.11-slim",
            command=["sh", "-c", "pip install pytest -q && pytest -v"],
            detach=True,
            remove=False,
            volumes={
                str(workspace.resolve()): {"bind": "/workspace", "mode": "rw"},
            },
            working_dir="/workspace",
        )
    except Exception as e:
        logger.exception("Error starting container: %s", e)
        return {
            "exit_code": -1,
            "logs": "",
            "error": f"Failed to start container: {e}",
        }

    if container is None:
        return {"exit_code": -1, "logs": "", "error": "Failed to start container"}

    try:
        result = container.wait()
        exit_code = (
            result.get("StatusCode", -1)
            if isinstance(result, dict)
            else (result if isinstance(result, int) else -1)
        )
        logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
    except Exception as e:
        logger.exception("Error waiting for container or reading logs: %s", e)
        logs = str(e)
        exit_code = -1
    finally:
        try:
            container.remove(force=True)
        except Exception as e:
            logger.warning("Failed to remove container: %s", e)

    return {
        "exit_code": exit_code,
        "logs": logs,
        "error": None,
    }
