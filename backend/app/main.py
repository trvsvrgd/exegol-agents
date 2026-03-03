from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.graph import run_graph

# Load .env from backend/ so LangSmith and other vars work
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title="Exegol V2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    prompt: str


@app.get("/")
async def root():
    return {"message": "Hello from Exegol"}


@app.post("/api/run")
async def run(request: RunRequest):
    result = run_graph(request.prompt)
    return result
