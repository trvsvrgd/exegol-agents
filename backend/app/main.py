import ast
import asyncio
import json
import os
import queue
import re
import threading
import uuid
from collections import deque
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.graph import build_and_stream_graph, stream_resume_graph
from app.logging_config import LOG_PATH
from app.memory.vector_store import add_to_memory, TYPE_SOP

# Load .env from backend/ so LangSmith and other vars work
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title="Exegol V2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory execution state for polling
_execution_state: dict = {
    "status": "idle",
    "current_node": None,
    "messages": [],
    "current_plan": "",
    "evaluation_result": None,
}
_state_lock = threading.Lock()

# SSE broadcast: background thread pushes state to these queues
_sse_queues: list[queue.Queue] = []
_sse_lock = threading.Lock()


def _broadcast_state() -> None:
    """Push current execution state to all SSE listeners."""
    with _state_lock:
        snapshot = {k: v for k, v in _execution_state.items()}
    with _sse_lock:
        for q in _sse_queues:
            try:
                q.put_nowait(snapshot)
            except queue.Full:
                pass


class RunRequest(BaseModel):
    prompt: str


class DecisionRequest(BaseModel):
    thread_id: str
    decision: str  # "approve" | "edit" | "reject"
    edited_plan: str | None = None


class CoachRequest(BaseModel):
    """Request body for Agent Manager coaching: add a correction as a new SOP."""

    correction: str  # The SOP/correction to remember (required)
    drifted_context: str | None = None  # What the agent did wrong (optional)
    thread_id: str | None = None  # Optional traceability


def _apply_state_update(update: dict) -> None:
    """Apply a state update to _execution_state (caller holds _state_lock)."""
    if "messages" in update and update["messages"]:
        _execution_state["messages"] = update["messages"]
    if "current_plan" in update and update.get("current_plan") is not None:
        _execution_state["current_plan"] = update["current_plan"]
    if "routed_intent" in update and update.get("routed_intent") is not None:
        _execution_state["routed_intent"] = update["routed_intent"]
    if "evaluation_result" in update and update.get("evaluation_result") is not None:
        _execution_state["evaluation_result"] = update["evaluation_result"]


def _run_graph_background(prompt: str, thread_id: str) -> None:
    """Run graph in thread and update _execution_state for polling and SSE."""
    with _state_lock:
        _execution_state["status"] = "running"
        _execution_state["current_node"] = "router"
        _execution_state["messages"] = [{"role": "user", "content": prompt}]
        _execution_state["current_plan"] = ""
        _execution_state["evaluation_result"] = None
        _execution_state["thread_id"] = thread_id
        _execution_state.pop("__interrupt__", None)
    _broadcast_state()

    try:
        for node_name, state in build_and_stream_graph(prompt, thread_id=thread_id):
            if node_name == "__interrupt__":
                with _state_lock:
                    _execution_state["status"] = "awaiting_approval"
                    _execution_state["current_node"] = "approval"
                    if isinstance(state, dict) and "merged" in state:
                        _apply_state_update(state["merged"])
                    _execution_state["__interrupt__"] = state.get("interrupt", state)
                    _execution_state["thread_id"] = state.get("thread_id", thread_id)
                _broadcast_state()
                return

            with _state_lock:
                _execution_state["current_node"] = node_name
                _apply_state_update(state if isinstance(state, dict) else {})
            _broadcast_state()

        with _state_lock:
            _execution_state["status"] = "done"
        _broadcast_state()
    except Exception as e:
        with _state_lock:
            _execution_state["status"] = "error"
            _execution_state["error"] = str(e)
        _broadcast_state()


def _run_resume_background(thread_id: str, decision: str, edited_plan: str | None) -> None:
    """Resume graph after human decision and update _execution_state."""
    with _state_lock:
        _execution_state["status"] = "running"
        _execution_state["current_node"] = "approval"
        _execution_state["thread_id"] = thread_id
    _broadcast_state()

    try:
        for node_name, state in stream_resume_graph(
            thread_id, decision=decision, edited_plan=edited_plan
        ):
            if node_name == "__interrupt__":
                with _state_lock:
                    _execution_state["status"] = "awaiting_approval"
                    if isinstance(state, dict) and "merged" in state:
                        _apply_state_update(state["merged"])
                    _execution_state["__interrupt__"] = state.get("interrupt", state)
                    _execution_state["thread_id"] = state.get("thread_id", thread_id)
                _broadcast_state()
                return

            with _state_lock:
                _execution_state["current_node"] = node_name
                _apply_state_update(state if isinstance(state, dict) else {})
            _broadcast_state()

        with _state_lock:
            _execution_state["status"] = "done"
        _broadcast_state()
    except Exception as e:
        with _state_lock:
            _execution_state["status"] = "error"
            _execution_state["error"] = str(e)
        _broadcast_state()


@app.get("/")
async def root():
    return {"message": "Hello from Exegol"}


def _check_ollama() -> tuple[bool, str]:
    """Check if Ollama is reachable. Returns (ok, message)."""
    try:
        req = Request("http://localhost:11434/api/tags", method="GET")
        with urlopen(req, timeout=3) as r:
            if r.status == 200:
                return True, "Ollama is running"
            return False, f"Ollama returned status {r.status}"
    except URLError as e:
        return False, "Ollama is not running. Start it with: ollama serve"
    except Exception as e:
        return False, str(e)


def _check_docker() -> tuple[bool, str]:
    """Check if Docker is running and the sandbox image exists. Returns (ok, message)."""
    try:
        import docker
    except ImportError:
        return False, "Docker SDK not installed. pip install docker"
    try:
        client = docker.from_env()
        client.ping()
    except docker.errors.DockerException as e:
        return False, f"Docker not available: {e}. Start Docker Desktop or the Docker daemon."
    except Exception as e:
        return False, str(e)
    # Check if sandbox image exists
    import json
    from pathlib import Path
    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "sandbox.json"
    image = "exegol-sandbox-mcp:latest"
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                cfg = json.load(f)
            image = cfg.get("image", image)
        except (json.JSONDecodeError, OSError):
            pass
    try:
        client.images.get(image)
        return True, f"Docker ok, image {image} found"
    except docker.errors.ImageNotFound:
        return False, f"Sandbox image not found. Build it: docker build -f Dockerfile.sandbox -t {image} ."
    except Exception as e:
        return False, str(e)


def _check_langsmith_config() -> tuple[bool, str | None]:
    """
    Check LangSmith config. Returns (ok, warning_message).
    If tracing is on but API key is blank, returns (True, warning) so the app runs but user is informed.
    """
    tracing = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes")
    api_key = (os.getenv("LANGCHAIN_API_KEY") or "").strip()
    if tracing and not api_key:
        return True, (
            "LangSmith tracing is enabled but LANGCHAIN_API_KEY is empty. "
            "Option A: Set LANGCHAIN_API_KEY in backend/.env (see backend/.env.example). "
            "Option B: Set LANGCHAIN_TRACING_V2=false in backend/.env to disable tracing."
        )
    return True, None


@app.get("/api/health")
async def get_health():
    """
    Return health status of required and optional services.
    Used by the frontend to show clear error messages when components are missing.
    """
    ollama_ok, ollama_msg = await asyncio.to_thread(_check_ollama)
    docker_ok, docker_msg = await asyncio.to_thread(_check_docker)
    langsmith_ok, langsmith_warning = _check_langsmith_config()
    return {
        "backend": "ok",
        "ollama": {"ok": ollama_ok, "message": ollama_msg},
        "docker": {"ok": docker_ok, "message": docker_msg},
        "langsmith": {
            "ok": langsmith_ok,
            "warning": langsmith_warning,
        },
        "warnings": [w for w in [langsmith_warning] if w],
    }


@app.get("/api/status")
async def get_status():
    """Return the latest graph execution state for the dashboard."""
    with _state_lock:
        out = {k: v for k, v in _execution_state.items()}
    return out


def _sse_event_generator():
    """Generator for SSE stream. Runs in thread; yields raw SSE bytes."""
    client_queue: queue.Queue = queue.Queue(maxsize=64)
    with _sse_lock:
        _sse_queues.append(client_queue)
    try:
        # Send initial state
        with _state_lock:
            snapshot = {k: v for k, v in _execution_state.items()}
        yield f"data: {json.dumps(snapshot)}\n\n"
        # Stream updates (block with timeout for keepalive)
        while True:
            try:
                data = client_queue.get(timeout=15)
                yield f"data: {json.dumps(data)}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"
    finally:
        with _sse_lock:
            if client_queue in _sse_queues:
                _sse_queues.remove(client_queue)


@app.get("/api/status/stream")
async def stream_status():
    """Stream graph execution state via Server-Sent Events for real-time UI updates."""
    return StreamingResponse(
        _sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/plan")
async def get_plan():
    """Return the raw markdown from workspace/plan.md."""
    plan_path = Path(__file__).resolve().parent.parent.parent / "workspace" / "plan.md"
    try:
        return {"content": plan_path.read_text(encoding="utf-8")}
    except FileNotFoundError:
        return {"content": ""}
    except OSError as e:
        return {"content": "", "error": str(e)}


# Log line format: timestamp | level | thread_id=XXX | message
# message can be: "node=NAME event=start" or "node=NAME event=end duration_sec=X.XXX token_usage={...} tool_calls=N"
_LOG_LINE_RE = re.compile(
    r"^(.+?)\s*\|\s*(\w+)\s*\|\s*thread_id=([^\s|]+)\s*\|\s*(.*)$"
)
_NODE_EVENT_RE = re.compile(
    r"node=(\S+)\s+event=(\w+)(?:\s+duration_sec=([\d.]+))?(?:\s+token_usage=(\{[^{}]+\}))?(?:\s+tool_calls=(\d+))?"
)
_TOKEN_USAGE_RE = re.compile(r"^\{.+\}$")


def _parse_log_line(line: str) -> dict | None:
    """Parse a single exegol.log line into a structured dict, or None if unparseable."""
    line = line.strip()
    if not line:
        return None
    m = _LOG_LINE_RE.match(line)
    if not m:
        return {"raw": line}
    ts, level, thread_id, msg = m.groups()
    entry: dict = {
        "timestamp": ts.strip(),
        "level": level,
        "thread_id": thread_id.strip(),
        "message": msg.strip(),
    }
    msg_stripped = msg.strip()
    ne = _NODE_EVENT_RE.match(msg_stripped)
    if ne:
        entry["node"] = ne.group(1)
        entry["event"] = ne.group(2)
        if ne.group(3):
            try:
                entry["duration_sec"] = float(ne.group(3))
            except (TypeError, ValueError):
                pass
        tu_str = ne.group(4)
        if tu_str and _TOKEN_USAGE_RE.search(tu_str):
            try:
                entry["token_usage"] = ast.literal_eval(tu_str)
            except (ValueError, SyntaxError):
                pass
        if ne.group(5):
            try:
                entry["tool_calls"] = int(ne.group(5))
            except (TypeError, ValueError):
                pass
    else:
        tc_match = re.search(r"tool_calls=(\d+)", msg_stripped)
        if tc_match:
            try:
                entry["tool_calls"] = int(tc_match.group(1))
            except ValueError:
                pass
        dur_match = re.search(r"duration_sec=([\d.]+)", msg_stripped)
        if dur_match:
            try:
                entry["duration_sec"] = float(dur_match.group(1))
            except (TypeError, ValueError):
                pass
    return entry


@app.get("/api/telemetry")
async def get_telemetry():
    """Return the last 100 lines of exegol.log parsed into a JSON array for token usage and latency metrics."""
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            lines = deque(f, maxlen=100)
    except FileNotFoundError:
        return {"entries": []}
    except OSError as e:
        return {"entries": [], "error": str(e)}

    entries = []
    for line in lines:
        parsed = _parse_log_line(line)
        if parsed:
            entries.append(parsed)
    return {"entries": entries}


def _compute_drift_metrics(entries: list[dict]) -> dict:
    """
    Aggregate log entries into drift metrics for the Manager Dashboard.
    Tracks: latency by node, token usage trends, redundant tool usage, reasoning coherence.
    """
    from collections import defaultdict
    from datetime import datetime

    # Group end events by thread (sessions)
    sessions: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        if e.get("event") != "end":
            continue
        tid = e.get("thread_id", "-")
        if tid == "-":
            continue
        sessions[tid].append(e)

    # Latency by node (all sessions)
    latency_by_node: dict[str, list[float]] = defaultdict(list)
    token_by_node: dict[str, list[int]] = defaultdict(list)
    tool_calls_per_coder: list[int] = []

    for tid, evts in sessions.items():
        coder_count = 0
        evaluator_count = 0
        for e in evts:
            node = e.get("node", "")
            dur = e.get("duration_sec")
            if dur is not None:
                latency_by_node[node].append(dur)
            tu = e.get("token_usage") or {}
            total_tok = tu.get("total") or (
                (tu.get("prompt_eval_count") or 0) + (tu.get("eval_count") or 0)
            )
            if total_tok:
                token_by_node[node].append(total_tok)
            tc = e.get("tool_calls")
            if node == "coder":
                coder_count += 1
                if tc is not None:
                    tool_calls_per_coder.append(tc)
            elif node == "evaluator":
                evaluator_count += 1

        # Sessions with >1 coder run had evaluator retries (reasoning coherence proxy)
        # Redundant tool usage: high tool calls per coder run

    # Compute stats
    def _percentile(arr: list[float], p: float) -> float | None:
        if not arr:
            return None
        s = sorted(arr)
        idx = max(0, int(len(s) * p / 100) - 1)
        return s[min(idx, len(s) - 1)]

    def _avg(arr: list) -> float | None:
        if not arr:
            return None
        return sum(arr) / len(arr)

    latency_series: dict[str, dict] = {}
    for node, durs in latency_by_node.items():
        if durs:
            latency_series[node] = {
                "avg_sec": round(_avg(durs) or 0, 2),
                "p50_sec": round(_percentile(durs, 50) or 0, 2),
                "p95_sec": round(_percentile(durs, 95) or 0, 2),
                "count": len(durs),
            }

    token_series: dict[str, dict] = {}
    for node, toks in token_by_node.items():
        if toks:
            token_series[node] = {
                "avg_tokens": round(_avg(toks) or 0, 0),
                "total_tokens": sum(toks),
                "count": len(toks),
            }

    total_sessions = len(sessions)
    sessions_with_retries = sum(
        1 for evts in sessions.values()
        if sum(1 for e in evts if e.get("node") == "coder") > 1
    )
    retry_rate = (
        round(sessions_with_retries / total_sessions * 100, 1)
        if total_sessions else 0
    )

    return {
        "latency_by_node": latency_series,
        "token_usage_by_node": token_series,
        "redundant_tool_usage": {
            "avg_tool_calls_per_coder_run": round(
                _avg(tool_calls_per_coder) or 0, 1
            ),
            "max_tool_calls_in_run": max(tool_calls_per_coder, default=0),
            "coder_runs_with_tool_data": len(tool_calls_per_coder),
        },
        "reasoning_coherence": {
            "evaluator_pass_rate_pct": round(100 - retry_rate, 1),
            "sessions_with_retries": sessions_with_retries,
            "total_sessions": total_sessions,
        },
        "entries_analyzed": len([e for e in entries if e.get("event") == "end"]),
    }


@app.get("/api/drift")
async def get_drift():
    """
    Return aggregated drift metrics for the Manager Dashboard.
    Parses exegol.log to compute latency trends, token usage, redundant tool usage, and reasoning coherence.
    """
    try:
        with open(LOG_PATH, encoding="utf-8") as f:
            lines = list(f)
    except FileNotFoundError:
        return {
            "latency_by_node": {},
            "token_usage_by_node": {},
            "redundant_tool_usage": {"avg_tool_calls_per_coder_run": 0, "max_tool_calls_in_run": 0, "coder_runs_with_tool_data": 0},
            "reasoning_coherence": {"evaluator_pass_rate_pct": 0, "sessions_with_retries": 0, "total_sessions": 0},
            "entries_analyzed": 0,
            "error": "exegol.log not found",
        }
    except OSError as e:
        return {
            "latency_by_node": {},
            "token_usage_by_node": {},
            "redundant_tool_usage": {"avg_tool_calls_per_coder_run": 0, "max_tool_calls_in_run": 0, "coder_runs_with_tool_data": 0},
            "reasoning_coherence": {"evaluator_pass_rate_pct": 0, "sessions_with_retries": 0, "total_sessions": 0},
            "entries_analyzed": 0,
            "error": str(e),
        }

    entries = []
    for line in lines[-10000:]:
        parsed = _parse_log_line(line)
        if parsed:
            entries.append(parsed)

    return _compute_drift_metrics(entries)


@app.post("/api/run")
async def run(request: RunRequest, background_tasks: BackgroundTasks):
    thread_id = str(uuid.uuid4())
    background_tasks.add_task(_run_graph_background, request.prompt, thread_id)
    return {
        "status": "started",
        "thread_id": thread_id,
        "message": "Execution started. Poll /api/status for progress. When status is awaiting_approval, submit decision via POST /api/decision.",
    }


@app.post("/api/coach")
async def coach_agent(request: CoachRequest):
    """
    Agent Manager coaching: flag a drifted response and add a correction as a new SOP.
    The correction is written to the Coordinator's long-term vector memory and will
    be retrieved when relevant for future routing and planning.
    """
    correction = (request.correction or "").strip()
    if not correction:
        return {"status": "error", "message": "correction is required and cannot be empty"}

    metadata: dict = {"source": "coaching"}
    if request.drifted_context:
        metadata["drifted_context"] = request.drifted_context[:1000]
    if request.thread_id:
        metadata["thread_id"] = request.thread_id

    await asyncio.to_thread(
        add_to_memory,
        content=correction,
        doc_type=TYPE_SOP,
        metadata=metadata,
    )
    return {"status": "ok", "message": "SOP added to agent memory. Future runs will use this guidance."}


@app.post("/api/decision")
async def submit_decision(request: DecisionRequest, background_tasks: BackgroundTasks):
    """Submit approve, edit, or reject decision to resume the graph after HITL interrupt."""
    decision = request.decision.lower()
    if decision not in ("approve", "edit", "reject"):
        return {
            "status": "error",
            "message": "decision must be one of: approve, edit, reject",
        }

    if decision == "edit" and not request.edited_plan:
        return {
            "status": "error",
            "message": "edited_plan is required when decision is 'edit'",
        }

    background_tasks.add_task(
        _run_resume_background,
        request.thread_id,
        decision,
        request.edited_plan,
    )
    return {
        "status": "resumed",
        "thread_id": request.thread_id,
        "message": f"Decision '{decision}' submitted. Poll /api/status for progress.",
    }
