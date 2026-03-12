# Exegol V2 Evolution Roadmap (Updated)

*Internal development plan for the Exegol platform itself—not the user's workspace plan. User plans for agents and apps live in `workspace/plan.md` and are surfaced via the UI.*

## Phase 1: Local-First Orchestration & State (The App)
- [x] **Task 1.1: Local Planner Migration.** Swapped the Planner node's LLM from Gemini to local Ollama (qwen2.5-coder). Added PydanticOutputParser and `format="json"` for reliable structured JSON task output. Config: `config/agents.yaml`.
- [x] **Task 1.2: Graph Observability & Telemetry.** Local telemetry implemented via `app/logging_config.py`: structured logging to `exegol.log` with `thread_id`, node start/end, duration, and token usage (Ollama `prompt_eval_count`/`eval_count`). Wrapper in `graph.py` logs all nodes. Baseline for drift measurement.
- [x] **Task 1.3: Streaming State to UI.** Added `GET /api/status/stream` SSE endpoint in FastAPI that broadcasts execution state on each graph node transition. Frontend uses EventSource instead of polling; real-time updates for running/awaiting_approval/done/error.

## Phase 2: Orchestrator Maturation (The Coordinator)
- [x] **Task 2.1: Dynamic Routing.** Upgrade the Planner to a dynamic Router. Give the local model the ability to assess user intent and route tasks to specialized sub-agents rather than a linear pipeline.
- [x] **Task 2.2: Memory & Context.** Implement a local vector store (e.g., Chroma) so the Coordinator can retrieve past architectural decisions and standard operating procedures (SOPs).
- [x] **Task 2.3: Human-in-the-Loop (HITL) Checkpoints.** Implement LangGraph's `interrupt` capability before any high-stakes execution node. The graph pauses, persists its state with InMemorySaver, and waits for human approval via `POST /api/decision` (approve/edit/reject) before the Coder runs.

## Phase 3: The "Agent Manager" Lifecycle (Evaluation & Drift)
- [x] **Task 3.1: Session-Level Evaluation (The Evaluator Node).** Evaluator node in `app/nodes/evaluator_node.py` grades Coder output against user prompt and approved plan. Rubric: success/fail + feedback. Routes back to Coder on failure (max 3 retries via `retry_count` in state); routes to END on success.
- [x] **Task 3.2: Long-Term Drift Detection (The Manager Dashboard).** Create a dashboard in the Next.js UI that tracks "Behavioral Drift." Monitor metrics over time: frequency of redundant tool usage, latency degradation, and reasoning coherence across sessions.
- [x] **Task 3.3: The "Coaching" Mechanism.** Implement a feedback loop where the Agent Manager (you) can flag a drifted response in the UI, provide a text correction, and write that correction to the agent's long-term vector memory as a new SOP ("Standard Operating Procedure").

## Verification Evidence
- FastAPI app loads: `python -c "from app.main import app; print('OK')"` → OK
- Graph runs (Ollama): `run_graph("...")` invokes router → [approval→coder | explorer | END]

## Active Exceptions
- None

## Process Notes: Keeping PLAN.md in Sync
**Root cause (Task 1.2 was implemented but not marked complete):** The cursor rule says "update before new features" but does not explicitly require updating PLAN.md *after* completing a task. Agents given narrow, implementation-focused prompts (e.g. "Update backend/app/graph.py...") tend to deliver only the requested code changes and do not proactively update the roadmap. **Remedy:** When implementing any task that maps to a PLAN.md checklist item, mark it complete in the same session. See `.cursorrules` — consider strengthening to: "PLAN.md: Roadmap; update before new features and after completing any roadmap task."

## Future Enhancements (with prompts for incremental Cursor work)

*Use sections below for prompts; check status before implementing. Update status after completing.*

### E1. Start Development Script — DONE
`start_dev.ps1` exists and meets criteria: venv creation, FastAPI + Next.js in separate windows, browser opens. No action needed.

### E2. UI Thematic Updates (Lightning, Sith, Star Wars) — DONE
**Acceptance:** Lightning, Sith, Star Wars aesthetics; keep dark theme + red-amber-violet.
**Status:** Implemented: gradient overlays, lightning ⚡ accents, Orbitron typography, Sith/Imperial styling on both pages.

### E3. Evaluator Retry Limit — DONE
`retry_count` in state, `MAX_CODER_RETRIES = 3` in graph.py, enforced in `_route_after_evaluator`. Optional UX: surface "Coder exhausted retries" explicitly when limit reached.

### E4. API Key and Configuration Error Messaging — DONE
**Acceptance:** LangSmith tracing on + empty API key → clear warning with remediation (set key or LANGCHAIN_TRACING_V2=false).
**Status:** Option A/B steps on both dashboards; config help via backend/.env.example reference.

### E5. Mandatory Service Error Messages — DONE
**Acceptance:** Backend/Ollama/Docker down → clear message + next steps; Run button disabled.
**Status:** Unified System readiness panel on both Control and Manager dashboards. Correct commands: python3, ollama serve, ollama pull qwen2.5-coder, .\build_sandbox.ps1.

### E6. Documentation Drift — DONE
**Acceptance:** TECH_SPEC and README reflect Router→[Approval→Coder→Evaluator | Explorer | END]; no GOOGLE_API_KEY.
**Status:** TECH_SPEC and README updated with correct flow, nodes, and config.

### E7. PLAN.md Sync Process — DONE
**Acceptance:** Mark roadmap tasks complete in PLAN.md in same session; AGENTS.md/cursorrules require it.
**Status:** Added PLAN.md Sync section to AGENTS.md.

### Enhancement Summary
| E# | Enhancement              | Status     |
|----|--------------------------|------------|
| E1 | start_dev.ps1            | Done       |
| E2 | UI Thematic              | Done       |
| E3 | Evaluator retry limit    | Done       |
| E4 | API key messaging        | Done       |
| E5 | Service error messages   | Done       |
| E6 | Documentation drift      | Done       |
| E7 | PLAN.md sync process     | Done       |