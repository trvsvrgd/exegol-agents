# Exegol V2

Autonomous local agent orchestrator built with FastAPI, LangGraph, and Next.js. A planner (Ollama) decomposes user intent into tasks; a coder (Ollama) executes them locally.

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | Python, FastAPI, LangGraph, LangChain |
| LLMs | Ollama/qwen2.5-coder (planning and coding) |
| Frontend | Next.js (App Router), Tailwind CSS |

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.ai) with `qwen2.5-coder` for planner and coder (pull: `ollama pull qwen2.5-coder`)

### Backend

```bash
cd backend
cp .env.example .env   # Optional: LANGCHAIN_API_KEY for tracing
pip install -r requirements.txt
uvicorn app.main:app --reload
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
# Returns JSON with messages, current_plan, status
```

## Project Structure

```
├── backend/           # FastAPI + LangGraph
│   ├── app/
│   │   ├── graph.py   # StateGraph, run_graph()
│   │   ├── main.py    # API, POST /api/run
│   │   ├── state.py   # GraphState
│   │   └── nodes/     # planner_node, coder_node, evaluator_node
│   └── requirements.txt
├── frontend/          # Next.js UI
├── config/            # agents.yaml, mcp_servers.json
├── workspace/         # plan.md
├── LOCAL_SETUP.md     # Detailed setup
├── TECH_SPEC.md       # Technical specification
└── PLAN.md            # Execution plan
```

## Flow

```
START → Planner (Ollama) → Coder (Ollama) → END
```

- **Planner**: Reads `workspace/plan.md`, uses local Ollama with structured output to decompose prompts into tasks.
- **Coder**: Executes tasks via Ollama with MCP filesystem tools.

## Configuration

- **Backend**: `backend/.env` (from `.env.example`) — `GOOGLE_API_KEY`, `LANGCHAIN_*`, etc.
- **Agents**: `config/agents.yaml`
- **MCP servers**: `config/mcp_servers.json`

See [LOCAL_SETUP.md](LOCAL_SETUP.md) for full setup details.
