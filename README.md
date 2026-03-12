# Exegol V2

Autonomous local agent orchestrator built with FastAPI, LangGraph, and Next.js. A Router (Ollama) assesses user intent and routes to specialized sub-agents: Approval → Coder → Evaluator, Explorer, or plan-only END.

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | Python, FastAPI, LangGraph, LangChain |
| LLMs | Ollama/qwen2.5-coder (routing, planning, coding, evaluation) |
| Frontend | Next.js (App Router), Tailwind CSS |

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.ai) with `qwen2.5-coder` (run `ollama pull qwen2.5-coder`)
- Docker (for Coder sandbox MCP; build with `.\build_sandbox.ps1`)

### Backend

```bash
cd backend
cp .env.example .env   # Optional: LANGCHAIN_API_KEY for tracing; or set LANGCHAIN_TRACING_V2=false
pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API: http://localhost:8000 · Docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:3000

### Verify

```bash
curl http://localhost:8000/
# {"message":"Hello from Exegol"}

curl -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Add a button"}'
# Returns JSON with status, thread_id, message
```

## Flow

```
START → Router (assess intent)
  → implement: Approval (HITL) → Coder → Evaluator → [END or retry Coder]
  → explore:   Explorer → END
  → plan_only: END
```

- **Router**: Uses local Ollama to assess intent (implement, explore, plan_only).
- **Approval**: Human-in-the-loop checkpoint before Coder runs. Approve, edit, or reject the plan.
- **Coder**: Executes tasks via Ollama with MCP sandbox tools.
- **Evaluator**: Grades Coder output; routes back to Coder on failure (max 3 retries).
- **Explorer**: Explores codebase without implementation.

## Configuration

- **Backend**: `backend/.env` (from `.env.example`) — `LANGCHAIN_*` for tracing. No cloud API keys required.
- **Agents**: `config/agents.yaml` (model names, etc.)
- **MCP servers**: `config/mcp_servers.json`
- **Sandbox**: `config/sandbox.json`; build image with `.\build_sandbox.ps1`

See [AGENTS.md](AGENTS.md) for service commands and [LOCAL_SETUP.md](LOCAL_SETUP.md) for full setup details.
