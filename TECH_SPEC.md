# Exegol V2 Technical Specification

## High-Level Intent
- Autonomous local agent orchestrator using FastAPI, LangGraph, and Next.js.
- Router (Ollama/qwen2.5-coder) assesses user intent and routes to specialized sub-agents; Coder (Ollama/qwen2.5-coder) executes implementation tasks.
- Local-first: Ollama for planning, routing, and coding. No cloud API keys required for core functionality.

## Core Requirements
- **Backend**: FastAPI, LangGraph StateGraph, CORS for `http://localhost:3000`.
- **State**: `messages`, `current_plan`, `status`, `routed_intent`, `retry_count`, `evaluation_result`.
- **Flow**: START → Router → [Approval → Coder → Evaluator | Explorer | END]. See Flow section.
- **Secrets**: Env-driven via `python-dotenv` from `backend/.env`. No hardcoded keys. No GOOGLE_API_KEY.
- **Tracing**: LangSmith when `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` set.

## Tech Stack
- **Backend**: Python 3.x, FastAPI, uvicorn, LangGraph, langchain-community.
- **LLMs**: ChatOllama (qwen2.5-coder @ localhost:11434) for router, approval, coder, evaluator, explorer.
- **Frontend**: Next.js (App Router, Tailwind CSS).
- **Config**: `config/agents.yaml`, `config/mcp_servers.json`, `config/sandbox.json`, `workspace/plan.md`.

## Flow (Router → Sub-Agents)
```
START
  → router_node      Assesses intent (implement | plan_only | explore)
  → (conditional)
      - plan_only    → END
      - explore      → explorer_node → END
      - implement    → approval_node (HITL interrupt)
                        → (approve) → coder_node → evaluator_node
                                        → (pass) → END
                                        → (fail, retries < 3) → coder_node
                                        → (fail, retries ≥ 3) → END
                        → (reject)  → rejected_node → END
                        → (edit)    → coder_node (with edited plan) → evaluator_node → ...
```

## Key Modules
- `app/main.py`: FastAPI app, CORS, POST `/api/run`, POST `/api/decision`, GET `/api/health`, GET `/api/drift`, POST `/api/coach`.
- `app/graph.py`: StateGraph definition, `build_and_stream_graph`, `stream_resume_graph`, `run_graph`, `resume_graph`.
- `app/state.py`: `GraphState` TypedDict.
- `app/nodes/router_node.py`: Assesses intent, routes to approval/explorer/end.
- `app/nodes/approval_node.py`: Human-in-the-loop; interrupts before Coder, accepts approve/edit/reject.
- `app/nodes/coder_node.py`: Executes task via Ollama + MCP sandbox.
- `app/nodes/evaluator_node.py`: Grades Coder output; routes back to Coder on failure (max 3 retries) or to END on success.
- `app/nodes/explorer_node.py`: Explores codebase (no implementation).
- `app/nodes/rejected_node.py`: Handles rejected plans.

## Testing Standards
- **Framework**: pytest.
- **Coverage**: Graph wiring, state transitions, API contract.
- **Success**: `pytest tests/` passes; `/api/run` returns structured result.

## Out of Scope (Current Phase)
- Production auth, multi-tenant deployment.

## SOC 2 Exception Log
- *None*
