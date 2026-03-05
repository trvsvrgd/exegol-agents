# Exegol V2 Evolution Roadmap (Updated)

*Internal development plan for the Exegol platform itself—not the user's workspace plan. User plans for agents and apps live in `workspace/plan.md` and are surfaced via the UI.*

## Phase 1: Local-First Orchestration & State (The App)
- [x] **Task 1.1: Local Planner Migration.** Swapped the Planner node's LLM from Gemini to local Ollama (qwen2.5-coder). Added PydanticOutputParser and `format="json"` for reliable structured JSON task output. Config: `config/agents.yaml`.
- [ ] **Task 1.2: Graph Observability & Telemetry.** Integrate LangSmith (or a local telemetry equivalent) to track the LangGraph execution path, latency, and token usage. We need a baseline to measure future drift.
- [ ] **Task 1.3: Streaming State to UI.** Update the FastAPI backend to stream LangGraph state changes to the Next.js frontend via Server-Sent Events, providing real-time visibility into the local models' execution.

## Phase 2: Orchestrator Maturation (The Coordinator)
- [ ] **Task 2.1: Dynamic Routing.** Upgrade the Planner to a dynamic Router. Give the local model the ability to assess user intent and route tasks to specialized sub-agents rather than a linear pipeline.
- [ ] **Task 2.2: Memory & Context.** Implement a local vector store (e.g., Chroma) so the Coordinator can retrieve past architectural decisions and standard operating procedures (SOPs).
- [x] **Task 2.3: Human-in-the-Loop (HITL) Checkpoints.** Implement LangGraph's `interrupt` capability before any high-stakes execution node. The graph pauses, persists its state with InMemorySaver, and waits for human approval via `POST /api/decision` (approve/edit/reject) before the Coder runs.

## Phase 3: The "Agent Manager" Lifecycle (Evaluation & Drift)
- [ ] **Task 3.1: Session-Level Evaluation (The Evaluator Node).** Build an internal Evaluator node that runs after the Coder. It must grade the execution against the original prompt using a strict rubric (Task Success, Tool Error Rate). If it fails, it routes back to the Coder.
- [ ] **Task 3.2: Long-Term Drift Detection (The Manager Dashboard).** Create a dashboard in the Next.js UI that tracks "Behavioral Drift." Monitor metrics over time: frequency of redundant tool usage, latency degradation, and reasoning coherence across sessions.
- [ ] **Task 3.3: The "Coaching" Mechanism.** Implement a feedback loop where the Agent Manager (you) can flag a drifted response in the UI, provide a text correction, and write that correction to the agent's long-term vector memory as a new SOP ("Standard Operating Procedure").

## Verification Evidence
- FastAPI app loads: `python -c "from app.main import app; print('OK')"` → OK
- Graph runs (Ollama): `run_graph("...")` invokes planner → coder

## Active Exceptions
- None

## Future Enhancements
- Enhancement: Create a start_dev.ps1 script at the root of the project that automatically:Checks if the backend venv exists (creates it if it doesn't).Activates the venv and starts the FastAPI server in the background.Navigates to the frontend folder and runs npm run dev.Opens your browser to the local Next.js dashboard.This turns a multi-terminal startup process into a single double-click.
- UI updates to thematically incorporate, lightning, sith, and star wars aesthetics
- If the Coder repeatedly fails the Evaluator's checks, the local model could spin endlessly. It is highly recommended to add a retry_count integer to your GraphState in backend/app/state.py and enforce a hard limit (e.g., max 3 loops) before forcing the graph to END.