import ast
import re
import threading
import uuid
from collections import deque
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.graph import build_and_stream_graph, stream_resume_graph
from app.logging_config import LOG_PATH

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


class RunRequest(BaseModel):
    prompt: str


class DecisionRequest(BaseModel):
    thread_id: str
    decision: str  # "approve" | "edit" | "reject"
    edited_plan: str | None = None


def _apply_state_update(update: dict) -> None:
    """Apply a state update to _execution_state (caller holds _state_lock)."""
    if "messages" in update and update["messages"]:
        _execution_state["messages"] = update["messages"]
    if "current_plan" in update and update.get("current_plan") is not None:
        _execution_state["current_plan"] = update["current_plan"]
    if "evaluation_result" in update and update.get("evaluation_result") is not None:
        _execution_state["evaluation_result"] = update["evaluation_result"]


def _run_graph_background(prompt: str, thread_id: str) -> None:
    """Run graph in thread and update _execution_state for polling."""
    with _state_lock:
        _execution_state["status"] = "running"
        _execution_state["current_node"] = "planner"
        _execution_state["messages"] = [{"role": "user", "content": prompt}]
        _execution_state["current_plan"] = ""
        _execution_state["evaluation_result"] = None
        _execution_state["thread_id"] = thread_id
        _execution_state.pop("__interrupt__", None)

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
                return

            with _state_lock:
                _execution_state["current_node"] = node_name
                _apply_state_update(state if isinstance(state, dict) else {})

        with _state_lock:
            _execution_state["status"] = "done"
    except Exception as e:
        with _state_lock:
            _execution_state["status"] = "error"
            _execution_state["error"] = str(e)


def _run_resume_background(thread_id: str, decision: str, edited_plan: str | None) -> None:
    """Resume graph after human decision and update _execution_state."""
    with _state_lock:
        _execution_state["status"] = "running"
        _execution_state["current_node"] = "approval"
        _execution_state["thread_id"] = thread_id

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
                return

            with _state_lock:
                _execution_state["current_node"] = node_name
                _apply_state_update(state if isinstance(state, dict) else {})

        with _state_lock:
            _execution_state["status"] = "done"
    except Exception as e:
        with _state_lock:
            _execution_state["status"] = "error"
            _execution_state["error"] = str(e)


@app.get("/")
async def root():
    return {"message": "Hello from Exegol"}


@app.get("/api/status")
async def get_status():
    """Return the latest graph execution state for the dashboard."""
    with _state_lock:
        out = {k: v for k, v in _execution_state.items()}
    return out


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
# message can be: "node=NAME event=start" or "node=NAME event=end duration_sec=X.XXX token_usage={...}"
_LOG_LINE_RE = re.compile(
    r"^(.+?)\s*\|\s*(\w+)\s*\|\s*thread_id=([^\s|]+)\s*\|\s*(.*)$"
)
_NODE_EVENT_RE = re.compile(r"node=(\S+)\s+event=(\w+)(?:\s+duration_sec=([\d.]+))?(?:\s+token_usage=(.+))?$")
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
    # Parse node/event/duration/token_usage from message
    ne = _NODE_EVENT_RE.match(msg.strip())
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


@app.post("/api/run")
async def run(request: RunRequest, background_tasks: BackgroundTasks):
    thread_id = str(uuid.uuid4())
    background_tasks.add_task(_run_graph_background, request.prompt, thread_id)
    return {
        "status": "started",
        "thread_id": thread_id,
        "message": "Execution started. Poll /api/status for progress. When status is awaiting_approval, submit decision via POST /api/decision.",
    }


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
