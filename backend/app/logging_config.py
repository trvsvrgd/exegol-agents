"""Structured logging for Exegol graph execution. Logs to exegol.log with thread_id for tracing."""

import logging
import time
from pathlib import Path

# exegol.log in project root (workspace sibling to backend/)
LOG_PATH = Path(__file__).resolve().parent.parent.parent / "exegol.log"
LOGGER_NAME = "exegol"

# Key for LLM nodes to pass token usage to the graph wrapper (stripped before state merge)
LOG_TOKEN_USAGE_KEY = "_log_token_usage"
# Key for Coder to pass tool call count to the graph wrapper (stripped before state merge)
LOG_TOOL_CALLS_KEY = "_log_tool_calls"

# Format: timestamp | level | thread_id | message
_LOG_FORMAT = "%(asctime)s | %(levelname)s | thread_id=%(thread_id)s | %(message)s"


def _ensure_thread_id(extra: dict | None, thread_id: str | None) -> dict:
    """Ensure thread_id is in extra for formatter. Default to '-' if missing."""
    out = dict(extra or {})
    out.setdefault("thread_id", thread_id or "-")
    return out


def configure_logging() -> logging.Logger:
    """Configure and return the Exegol logger. Idempotent."""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    class ThreadIdFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            if not hasattr(record, "thread_id"):
                record.thread_id = "-"
            return super().format(record)

    formatter = ThreadIdFormatter(_LOG_FORMAT)

    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def log_node_start(node_name: str, thread_id: str | None = None) -> None:
    """Log the start of a node execution."""
    logger = configure_logging()
    logger.info(
        f"node={node_name} event=start",
        extra=_ensure_thread_id({"thread_id": thread_id or "-"}, thread_id),
    )


def log_node_end(
    node_name: str,
    thread_id: str | None,
    duration_sec: float,
    token_usage: dict | None = None,
    tool_calls: int | None = None,
) -> None:
    """Log the end of a node execution with duration, optional token usage, and optional tool call count."""
    logger = configure_logging()
    extra = _ensure_thread_id({"thread_id": thread_id or "-"}, thread_id)
    parts = [f"node={node_name} event=end duration_sec={duration_sec:.3f}"]
    if token_usage:
        parts.append(f"token_usage={token_usage}")
    if tool_calls is not None:
        parts.append(f"tool_calls={tool_calls}")
    logger.info(
        " ".join(parts),
        extra=extra,
    )


def extract_usage_from_response(response) -> dict | None:
    """
    Extract token usage from LangChain AIMessage response_metadata.
    Returns dict with prompt_eval_count, eval_count (and total if derivable) or None.
    """
    if response is None:
        return None
    meta = getattr(response, "response_metadata", None) or {}
    if not isinstance(meta, dict):
        return None
    prompt = meta.get("prompt_eval_count")
    eval_count = meta.get("eval_count")
    if prompt is None and eval_count is None:
        return None
    out = {}
    if prompt is not None:
        out["prompt_eval_count"] = prompt
    if eval_count is not None:
        out["eval_count"] = eval_count
    if prompt is not None and eval_count is not None:
        out["total"] = prompt + eval_count
    return out if out else None
