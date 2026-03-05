# Agents

## Cursor Cloud specific instructions

### Services overview

| Service | Port | Command | Notes |
|---------|------|---------|-------|
| FastAPI backend | 8000 | `cd backend && python3 -m uvicorn app.main:app --reload` | Planner and coder use local Ollama; no cloud API keys required for `/api/run` |
| Next.js frontend | 3000 | `cd frontend && npm run dev` | Control dashboard: chat, activity feed, plan viewer |

### Running the backend

- Start from the `backend/` directory: `python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- `GET /` returns `{"message":"Hello from Exegol"}` — use this to verify the server is up.
- `GET /api/status` returns the latest graph execution state (for dashboard polling).
- `GET /api/plan` returns the raw markdown from `workspace/plan.md`.
- `POST /api/run` runs in background; poll `/api/status` for progress. Requires Ollama with `qwen2.5-coder` (or model in `config/agents.yaml`).
- If `backend/.env` doesn't exist, copy from `backend/.env.example`. **Never overwrite an existing `.env`** — it may contain user-configured secrets like `LANGCHAIN_API_KEY`. Instead, only add missing keys.

### Running the frontend

- Start from the `frontend/` directory: `npm run dev`
- Uses `package-lock.json` — always use `npm` (not pnpm/yarn).

### Lint

- Frontend: `cd frontend && npx eslint .`
- Backend: no linter configured; verify imports with `python3 -c "from app.main import app"` from `backend/`.

### Tests

- `pytest` is listed in `backend/requirements.txt` but no `tests/` directory exists yet (Phase 2 roadmap).
- Run from `backend/`: `python3 -m pytest tests/ -v` (once tests are created).

### Gotchas

- System Python is `python3`, not `python` — always use `python3` explicitly.
- **Planner and coder use local Ollama** (`qwen2.5-coder` by default). Configure model in `config/agents.yaml`. No Gemini/cloud API keys needed.
- **Sandbox MCP (Docker required)**: The Coder runs inside a containerized MCP server. Build the image first: `.\build_sandbox.ps1` or `docker build -f Dockerfile.sandbox -t exegol-sandbox-mcp:latest .`. Without it, the Run button is disabled and `/api/health` reports Docker/sandbox status.
- **LangSmith tracing**: keep `LANGCHAIN_TRACING_V2=true` (the default in `.env.example`) when `LANGCHAIN_API_KEY` is set. Traces go to the `exegol-v2` project in LangSmith. If `LANGCHAIN_API_KEY` is empty/missing, set `LANGCHAIN_TRACING_V2=false` to suppress 401 auth errors in logs.
