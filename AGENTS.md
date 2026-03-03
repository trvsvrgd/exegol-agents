# Agents

## Cursor Cloud specific instructions

### Services overview

| Service | Port | Command | Notes |
|---------|------|---------|-------|
| FastAPI backend | 8000 | `cd backend && python3 -m uvicorn app.main:app --reload` | Requires `backend/.env` with `GOOGLE_API_KEY` for `/api/run` |
| Next.js frontend | 3000 | `cd frontend && npm run dev` | Control dashboard: chat, activity feed, plan viewer |

### Running the backend

- Start from the `backend/` directory: `python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- `GET /` returns `{"message":"Hello from Exegol"}` — use this to verify the server is up.
- `GET /api/status` returns the latest graph execution state (for dashboard polling).
- `GET /api/plan` returns the raw markdown from `workspace/plan.md`.
- `POST /api/run` requires a valid `GOOGLE_API_KEY` in `backend/.env`. Without it, the endpoint returns 500. Runs in background; poll `/api/status` for progress.
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
- The original `gemini-1.5-flash` model has been removed from the API. The planner node now uses `gemini-2.5-flash`. If Gemini models change again, list available models with `python3 -c "from google import genai; import os; c = genai.Client(api_key=os.getenv('GOOGLE_API_KEY')); [print(m.name) for m in c.models.list() if 'flash' in m.name.lower()]"` from `backend/`.
- The free-tier Gemini API has a 20 requests/day limit per model. The graph's evaluator→planner loop can exhaust this quickly when Docker is not running (evaluator always fails → infinite loop). Use a billing-enabled API key for serious development.
- **`POST /api/run` infinite loop without Docker**: the evaluator node always returns `exit_code: -1` when Docker is unavailable, and the conditional edge routes back to the planner indefinitely. To test individual nodes without Docker, invoke them directly (see earlier tests in this session).
- The `GOOGLE_API_KEY` secret must be added to `backend/.env` for the full agent loop to work.
- **LangSmith tracing**: keep `LANGCHAIN_TRACING_V2=true` (the default in `.env.example`) when `LANGCHAIN_API_KEY` is set. Traces go to the `exegol-v2` project in LangSmith. If `LANGCHAIN_API_KEY` is empty/missing, set `LANGCHAIN_TRACING_V2=false` to suppress 401 auth errors in logs.
