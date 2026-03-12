# Exegol V2 Evolution Roadmap (Updated)

*Internal development plan for the Exegol platform itself—not the user's workspace plan. User plans for agents and apps live in `workspace/plan.md` and are surfaced via the UI.*

## Phase 1: Local-First Orchestration & State (The App)
- [x] **Task 1.1: Local Planner Migration.** Swapped the Planner node's LLM from Gemini to local Ollama (qwen2.5-coder). Added PydanticOutputParser and `format="json"` for reliable structured JSON task output. Config: `config/agents.yaml`.
- [x] **Task 1.2: Graph Observability & Telemetry.** Local telemetry implemented via `app/logging_config.py`: structured logging to `exegol.log` with `thread_id`, node start/end, duration, and token usage (Ollama `prompt_eval_count`/`eval_count`). Wrapper in `graph.py` logs all nodes. Baseline for drift measurement.
- [x] **Task 1.3: Streaming State to UI.** Added `GET /api/status/stream` SSE endpoint in FastAPI that broadcasts execution state on each graph node transition. Frontend uses EventSource instead of polling; real-time updates for running/awaiting_approval/done/error.

## Phase 2: Orchestrator Maturation (The Coordinator)
- [x] **Task 2.1: Dynamic Routing.** Upgrade the Planner to a dynamic Router. Give the local model the ability to assess user intent and route tasks to specialized sub-agents rather than a linear pipeline.
- [ ] **Task 2.2: Memory & Context.** Implement a local vector store (e.g., Chroma) so the Coordinator can retrieve past architectural decisions and standard operating procedures (SOPs).
- [x] **Task 2.3: Human-in-the-Loop (HITL) Checkpoints.** Implement LangGraph's `interrupt` capability before any high-stakes execution node. The graph pauses, persists its state with InMemorySaver, and waits for human approval via `POST /api/decision` (approve/edit/reject) before the Coder runs.

## Phase 3: The "Agent Manager" Lifecycle (Evaluation & Drift)
- [x] **Task 3.1: Session-Level Evaluation (The Evaluator Node).** Evaluator node in `app/nodes/evaluator_node.py` grades Coder output against user prompt and approved plan. Rubric: success/fail + feedback. Routes back to Coder on failure (max 3 retries via `retry_count` in state); routes to END on success.
- [ ] **Task 3.2: Long-Term Drift Detection (The Manager Dashboard).** Create a dashboard in the Next.js UI that tracks "Behavioral Drift." Monitor metrics over time: frequency of redundant tool usage, latency degradation, and reasoning coherence across sessions.
- [ ] **Task 3.3: The "Coaching" Mechanism.** Implement a feedback loop where the Agent Manager (you) can flag a drifted response in the UI, provide a text correction, and write that correction to the agent's long-term vector memory as a new SOP ("Standard Operating Procedure").

## Verification Evidence
- FastAPI app loads: `python -c "from app.main import app; print('OK')"` → OK
- Graph runs (Ollama): `run_graph("...")` invokes router → [approval→coder | explorer | END]

## Active Exceptions
- None

## Process Notes: Keeping PLAN.md in Sync
**Root cause (Task 1.2 was implemented but not marked complete):** The cursor rule says "update before new features" but does not explicitly require updating PLAN.md *after* completing a task. Agents given narrow, implementation-focused prompts (e.g. "Update backend/app/graph.py...") tend to deliver only the requested code changes and do not proactively update the roadmap. **Remedy:** When implementing any task that maps to a PLAN.md checklist item, mark it complete in the same session. See `.cursorrules` — consider strengthening to: "PLAN.md: Roadmap; update before new features and after completing any roadmap task."

## Future Enhancements
- Enhancement: Create a start_dev.ps1 script at the root of the project that automatically:Checks if the backend venv exists (creates it if it doesn't).Activates the venv and starts the FastAPI server in the background.Navigates to the frontend folder and runs npm run dev.Opens your browser to the local Next.js dashboard.This turns a multi-terminal startup process into a single double-click.
- UI updates to thematically incorporate, lightning, sith, and star wars aesthetics
- If the Coder repeatedly fails the Evaluator's checks, the local model could spin endlessly. It is highly recommended to add a retry_count integer to your GraphState in backend/app/state.py and enforce a hard limit (e.g., max 3 loops) before forcing the graph to END.
- API key errors should be clearly indicated to user's with next steps (e.g.-if the Langsmith API is true, but the API key is blank. User steps should be clear)
- if a service, frontend, docker, or other mandatory component of the application is not running, create an error message.