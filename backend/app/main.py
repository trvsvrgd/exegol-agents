import threading
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.graph import build_and_stream_graph

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


def _run_graph_background(prompt: str) -> None:
    """Run graph in thread and update _execution_state for polling."""
    with _state_lock:
        _execution_state["status"] = "running"
        _execution_state["current_node"] = "planner"
        _execution_state["messages"] = [{"role": "user", "content": prompt}]
        _execution_state["current_plan"] = ""
        _execution_state["evaluation_result"] = None

    try:
        for node_name, state in build_and_stream_graph(prompt):
            with _state_lock:
                _execution_state["current_node"] = node_name
                if "messages" in state and state["messages"]:
                    _execution_state["messages"] = state["messages"]
                if "current_plan" in state and state["current_plan"]:
                    _execution_state["current_plan"] = state["current_plan"]
                if "evaluation_result" in state and state["evaluation_result"]:
                    _execution_state["evaluation_result"] = state["evaluation_result"]
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


@app.post("/api/run")
async def run(request: RunRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_graph_background, request.prompt)
    return {"status": "started", "message": "Execution started. Poll /api/status for progress."}
