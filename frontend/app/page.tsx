"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { ApprovalPanel } from "./components/ApprovalPanel";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ExecutionStatus = "idle" | "running" | "done" | "error" | "awaiting_approval";

type InterruptValue = {
  type?: string;
  message?: string;
  plan?: string;
  task_description?: string;
  messages?: unknown[];
};

type InterruptItem = { value?: InterruptValue; id?: string };
type InterruptPayload = InterruptItem | InterruptItem[] | InterruptValue;

type StatusResponse = {
  status: ExecutionStatus;
  current_node: string | null;
  messages: Array<{ role: string; content: string }>;
  current_plan: string;
  evaluation_result: Record<string, unknown> | null;
  thread_id?: string;
  __interrupt__?: InterruptPayload;
  error?: string;
};

type PlanResponse = { content: string; error?: string };

function extractTaskDescription(interrupt: InterruptPayload | undefined): string {
  if (!interrupt) return "";
  const arr = Array.isArray(interrupt) ? interrupt : [interrupt];
  const first = arr[0];
  if (!first) return "";
  const payload = first && typeof first === "object" && "value" in first
    ? (first as InterruptItem).value
    : (first as InterruptValue);
  if (!payload || typeof payload !== "object") return "";
  const text =
    (payload as InterruptValue).task_description ??
    (payload as InterruptValue).plan ??
    "";
  return typeof text === "string" ? text : "";
}

const NODE_LABELS: Record<string, string> = {
  planner: "Planner is thinking...",
  approval: "Awaiting approval...",
  coder: "Coder is writing...",
  evaluator: "Evaluator is testing...",
};

function getStatusLabel(status: ExecutionStatus, node: string | null): string {
  if (status === "idle") return "Ready";
  if (status === "awaiting_approval") return "Awaiting approval";
  if (status === "running" && node && NODE_LABELS[node])
    return NODE_LABELS[node];
  if (status === "running") return "Running...";
  if (status === "done") return "Finished";
  if (status === "error") return "Error";
  return "Unknown";
}

export default function Dashboard() {
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [plan, setPlan] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`);
      if (res.ok) setStatus((await res.json()) as StatusResponse);
    } catch {
      // Ignore fetch errors during polling
    }
  }, []);

  const fetchPlan = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/plan`);
      if (res.ok) {
        const data = (await res.json()) as PlanResponse;
        setPlan(data.content ?? "");
      }
    } catch {
      setPlan("");
    }
  }, []);

  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => {
      fetchStatus();
      fetchPlan();
    }, 800);
  }, [fetchStatus, fetchPlan]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchPlan();
    return () => stopPolling();
  }, [fetchStatus, fetchPlan, stopPolling]);

  useEffect(() => {
    if (
      status?.status === "running" ||
      status?.status === "awaiting_approval"
    )
      startPolling();
    else if (status?.status === "done" || status?.status === "error") {
      stopPolling();
      fetchStatus();
      fetchPlan();
    }
  }, [status?.status, startPolling, stopPolling, fetchStatus, fetchPlan]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt.trim() }),
      });
      if (res.ok) {
        startPolling();
        fetchStatus();
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDecision = useCallback(
    async (
      decision: "approve" | "reject" | "edit",
      editedPlan?: string
    ) => {
      const threadId = status?.thread_id;
      if (!threadId) return;
      const res = await fetch(`${API_BASE}/api/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: threadId,
          decision,
          edited_plan: decision === "edit" ? editedPlan : undefined,
        }),
      });
      if (res.ok) {
        startPolling();
        fetchStatus();
      }
    },
    [status?.thread_id, startPolling, fetchStatus]
  );

  const lastUserMessage = status?.messages?.find((m) => m.role === "user");
  const lastAgentMessage = [...(status?.messages ?? [])]
    .reverse()
    .find((m) =>
      ["assistant", "planner", "coder"].includes(String(m.role))
    );
  const evalResult = status?.evaluation_result;

  return (
    <div className="flex h-screen flex-col bg-zinc-950 text-zinc-100">
      <header className="border-b border-zinc-800 px-6 py-4">
        <h1 className="text-xl font-semibold tracking-tight">
          Exegol Control Dashboard
        </h1>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* Main content: Activity Feed */}
        <main className="flex-1 flex flex-col min-w-0 border-r border-zinc-800">
          <div className="flex-1 overflow-auto p-6 space-y-6">
            <section>
              <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3">
                Status
              </h2>
              <div
                className={`rounded-lg border px-4 py-3 ${
                  status?.status === "running"
                    ? "border-blue-500/50 bg-blue-500/5"
                    : status?.status === "awaiting_approval"
                      ? "border-amber-500/50 bg-amber-500/5"
                      : status?.status === "done"
                        ? "border-emerald-500/30 bg-emerald-500/5"
                        : status?.status === "error"
                          ? "border-red-500/30 bg-red-500/5"
                          : "border-zinc-700 bg-zinc-900/50"
                }`}
              >
                <p className="font-medium">
                  {getStatusLabel(
                    status?.status ?? "idle",
                    status?.current_node ?? null
                  )}
                </p>
                {status?.error && (
                  <p className="mt-2 text-sm text-red-400">{status.error}</p>
                )}
              </div>
            </section>

            {status?.status === "awaiting_approval" && status?.thread_id && (
              <section>
                <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3">
                  Human-in-the-Loop Approval
                </h2>
                <ApprovalPanel
                  taskDescription={
                    extractTaskDescription(status.__interrupt__) ||
                    status.current_plan ||
                    ""
                  }
                  threadId={status.thread_id}
                  onSubmit={handleDecision}
                />
              </section>
            )}

            {lastUserMessage && (
              <section>
                <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3">
                  Prompt
                </h2>
                <div className="rounded-lg border border-zinc-700 bg-zinc-900/50 px-4 py-3">
                  <p className="whitespace-pre-wrap text-zinc-200">
                    {typeof lastUserMessage.content === "string"
                      ? lastUserMessage.content
                      : JSON.stringify(lastUserMessage.content)}
                  </p>
                </div>
              </section>
            )}

            {lastAgentMessage && (
              <section>
                <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3">
                  Output
                </h2>
                <div className="rounded-lg border border-zinc-700 bg-zinc-900/50 px-4 py-3">
                  <p className="whitespace-pre-wrap text-zinc-200">
                    {typeof lastAgentMessage.content === "string"
                      ? lastAgentMessage.content
                      : JSON.stringify(lastAgentMessage.content)}
                  </p>
                </div>
              </section>
            )}

            {evalResult && (
              <section>
                <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3">
                  Docker Test Results
                </h2>
                <div className="rounded-lg border border-zinc-700 bg-zinc-900/50 px-4 py-3 font-mono text-sm overflow-x-auto">
                  <pre className="whitespace-pre-wrap text-zinc-300">
                    {JSON.stringify(evalResult, null, 2)}
                  </pre>
                </div>
              </section>
            )}
          </div>

          {/* Chat / Command Input */}
          <div className="border-t border-zinc-800 p-4">
            <form onSubmit={handleSubmit} className="flex gap-3">
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Describe what you want Exegol to build..."
                className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-3 text-zinc-100 placeholder-zinc-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                disabled={
                  isSubmitting ||
                  status?.status === "running" ||
                  status?.status === "awaiting_approval"
                }
              />
              <button
                type="submit"
                disabled={
                  !prompt.trim() ||
                  isSubmitting ||
                  status?.status === "running" ||
                  status?.status === "awaiting_approval"
                }
                className="rounded-lg bg-blue-600 px-6 py-3 font-medium text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Run
              </button>
            </form>
          </div>
        </main>

        {/* Plan Viewer side panel */}
        <aside className="w-96 flex-shrink-0 flex flex-col border-l border-zinc-800">
          <div className="border-b border-zinc-800 px-4 py-3">
            <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider">
              Plan (workspace/plan.md)
            </h2>
          </div>
          <div className="flex-1 overflow-auto p-4">
            <div className="prose prose-invert prose-sm max-w-none">
              {plan ? (
                <pre className="whitespace-pre-wrap text-zinc-300 font-mono text-xs bg-zinc-900/50 rounded-lg p-4 border border-zinc-800">
                  {plan}
                </pre>
              ) : (
                <p className="text-zinc-500 text-sm">No plan yet.</p>
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
