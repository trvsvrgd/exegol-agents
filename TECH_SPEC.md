# Exegol V2 Technical Specification

## High-Level Intent
- Autonomous local agent orchestrator using FastAPI, LangGraph, and Next.js.
- Planner (Ollama/qwen2.5-coder) decomposes user intent into tasks; Coder (Ollama/qwen2.5-coder) executes them.
- Local-first: Ollama for both planning and coding.

## Core Requirements
- **Backend**: FastAPI, LangGraph StateGraph, CORS for `http://localhost:3000`.
- **State**: `messages`, `current_plan`, `status`.
- **Flow**: START → Planner → Coder → END.
- **Secrets**: Env-driven via `python-dotenv` from `backend/.env`. No hardcoded keys.
- **Tracing**: LangSmith when `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` set.

## Tech Stack
- **Backend**: Python 3.x, FastAPI, uvicorn, LangGraph, langchain-community.
- **LLMs**: ChatOllama (qwen2.5-coder @ localhost:11434) for planner and coder.
- **Frontend**: Next.js (App Router, Tailwind CSS).
- **Config**: `config/agents.yaml`, `config/mcp_servers.json`, `workspace/plan.md`.

## Key Modules
- `app/main.py`: FastAPI app, CORS, POST `/api/run`.
- `app/graph.py`: StateGraph definition, `run_graph(prompt)`.
- `app/state.py`: `GraphState` TypedDict.
- `app/nodes/planner_node.py`: Reads `workspace/plan.md`, outputs structured task via local Ollama (PydanticOutputParser).
- `app/nodes/coder_node.py`: Executes task (mock or Ollama).

## Testing Standards
- **Framework**: pytest.
- **Coverage**: Graph wiring, state transitions, API contract.
- **Success**: `pytest tests/` passes; `/api/run` returns structured result.

## Out of Scope (Current Phase)
- MCP server integration, Docker deployment, production auth.

## SOC 2 Exception Log
- *None*
