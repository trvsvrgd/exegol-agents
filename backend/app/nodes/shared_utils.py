"""Shared helpers for Ollama-based planner/evaluator nodes."""

from pathlib import Path

import yaml

DEFAULT_MODEL = "qwen2.5-coder"
DEFAULT_BASE_URL = "http://localhost:11434"
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config" / "agents.yaml"


def load_agent_config(
    agent_name: str,
    default_model: str = DEFAULT_MODEL,
    default_base_url: str = DEFAULT_BASE_URL,
) -> dict[str, str]:
    """Load per-agent model config from config/agents.yaml with safe defaults."""
    defaults = {"model": default_model, "base_url": default_base_url}
    if not _CONFIG_PATH.exists():
        return defaults
    try:
        data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        agent_cfg = data.get(agent_name, {})
        return {
            "model": agent_cfg.get("model", default_model),
            "base_url": agent_cfg.get("base_url", default_base_url),
        }
    except Exception:
        return defaults


def extract_json_object(raw: str) -> str:
    """Extract the first top-level JSON object from markdown-fenced model output."""
    text = raw.strip()
    if "```" not in text:
        return text

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text
