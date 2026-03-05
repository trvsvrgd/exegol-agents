# Exegol V2 Local Setup

## Prerequisites
- Python 3.10+
- Node.js 18+ (for frontend)
- Docker (required for Coder sandbox)
- Ollama with `qwen2.5-coder` for planner and coder (required for `/api/run`)

## 1. Backend Environment
1. Copy `backend/.env.example` to `backend/.env` and fill placeholders.
2. Set:
   - `LANGCHAIN_API_KEY` — LangSmith (optional, for tracing)
   - `LANGCHAIN_TRACING_V2=true` — enable tracing
   - `LANGCHAIN_PROJECT=exegol-v2`
3. Never commit `.env`. It is in `.gitignore`.

## 2. Backend Run
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
API: `http://localhost:8000`  
Docs: `http://localhost:8000/docs`

## 3. Frontend Run
```bash
cd frontend
npm install
npm run dev
```
App: `http://localhost:3000`

## 4. Ollama (Required)
- Install: https://ollama.ai
- Pull model: `ollama pull qwen2.5-coder`
- Planner and coder both use this model (configurable in `config/agents.yaml`)

## 5. Sandbox Docker Image (Required for Coder)
The Coder runs in an isolated container. Build the image:
```powershell
.\build_sandbox.ps1
```
Or manually:
```bash
docker build -f Dockerfile.sandbox -t exegol-sandbox-mcp:latest .
```
Config: `config/sandbox.json` (image name, workspace mount, network, timeouts)

## Verification
- `curl http://localhost:8000/` → `{"message":"Hello from Exegol"}`
- `curl -X POST http://localhost:8000/api/run -H "Content-Type: application/json" -d '{"prompt":"Add a button"}'` → JSON with messages, current_plan, status
