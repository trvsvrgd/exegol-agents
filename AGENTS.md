# Agents

## Cursor Cloud specific instructions

### Services overview

| Service | Port | Command | Notes |
|---------|------|---------|-------|
| FastAPI backend | 8000 | `cd backend && python3 -m uvicorn app.main:app --reload` | Requires `backend/.env` with `GOOGLE_API_KEY` for `/api/run` |
| Next.js frontend | 3000 | `cd frontend && npm run dev` | Boilerplate UI; no custom pages yet |

### Running the backend

- Start from the `backend/` directory: `python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- `GET /` returns `{"message":"Hello from Exegol"}` — use this to verify the server is up.
- `POST /api/run` requires a valid `GOOGLE_API_KEY` in `backend/.env`. Without it, the endpoint returns 500.
- If `backend/.env` doesn't exist, copy from `backend/.env.example`.

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
- The `/api/run` graph flow calls Google Gemini (planner), Ollama (coder), and Docker (evaluator). Only Gemini (`GOOGLE_API_KEY`) is required; Ollama and Docker errors are caught gracefully and returned in the response.
- The `GOOGLE_API_KEY` secret must be added to `backend/.env` for the full agent loop to work.
