"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type HealthResponse = {
  backend: string;
  ollama: { ok: boolean; message: string };
  docker: { ok: boolean; message: string };
  langsmith: { ok: boolean; warning: string | null };
  warnings: string[];
};

type DriftResponse = {
  latency_by_node: Record<
    string,
    { avg_sec: number; p50_sec: number; p95_sec: number; count: number }
  >;
  token_usage_by_node: Record<
    string,
    { avg_tokens: number; total_tokens: number; count: number }
  >;
  redundant_tool_usage: {
    avg_tool_calls_per_coder_run: number;
    max_tool_calls_in_run: number;
    coder_runs_with_tool_data: number;
  };
  reasoning_coherence: {
    evaluator_pass_rate_pct: number;
    sessions_with_retries: number;
    total_sessions: number;
  };
  entries_analyzed: number;
  error?: string;
};

const NODE_LABELS: Record<string, string> = {
  router: "Router",
  approval: "Approval",
  coder: "Coder",
  evaluator: "Evaluator",
  explorer: "Explorer",
  rejected: "Rejected",
};

function MetricCard({
  title,
  value,
  subtext,
  status,
}: {
  title: string;
  value: string | number;
  subtext?: string;
  status?: "good" | "warn" | "bad";
}) {
  const statusBorder =
    status === "good"
      ? "border-emerald-500/40"
      : status === "warn"
        ? "border-amber-500/40"
        : status === "bad"
          ? "border-red-500/40"
          : "border-[#1f1f24]";

  return (
    <div
      className={`rounded-lg border ${statusBorder} bg-zinc-900/50 px-4 py-3`}
    >
      <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
        {title}
      </p>
      <p className="mt-1 text-xl font-semibold text-zinc-100">{value}</p>
      {subtext && <p className="mt-0.5 text-xs text-zinc-400">{subtext}</p>}
    </div>
  );
}

function ManagerDashboardContent() {
  const [drift, setDrift] = useState<DriftResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [backendUnreachable, setBackendUnreachable] = useState(false);
  const [coachCorrection, setCoachCorrection] = useState("");
  const [coachContext, setCoachContext] = useState("");
  const [coachSubmitting, setCoachSubmitting] = useState(false);
  const [coachSuccess, setCoachSuccess] = useState<string | null>(null);
  const [coachError, setCoachError] = useState<string | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      if (res.ok) {
        setHealth((await res.json()) as HealthResponse);
        setBackendUnreachable(false);
      }
    } catch {
      setBackendUnreachable(true);
      setHealth(null);
    }
  }, []);

  const fetchDrift = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/drift`);
      if (res.ok) {
        const data = (await res.json()) as DriftResponse;
        setDrift(data);
        setError(null);
      } else {
        setError(`HTTP ${res.status}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch drift data");
      setDrift(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const h = setInterval(fetchHealth, 15000);
    return () => clearInterval(h);
  }, [fetchHealth]);

  useEffect(() => {
    fetchDrift();
    const t = setInterval(fetchDrift, 30000);
    return () => clearInterval(t);
  }, [fetchDrift]);

  const searchParams = useSearchParams();
  useEffect(() => {
    const ctx = searchParams.get("drifted_context");
    if (ctx) setCoachContext(ctx);
    const focus = searchParams.get("coach");
    if (focus === "1") setCoachSuccess(null);
  }, [searchParams]);

  const handleCoachSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const correction = coachCorrection.trim();
      if (!correction || coachSubmitting) return;
      setCoachSubmitting(true);
      setCoachSuccess(null);
      setCoachError(null);
      try {
        const res = await fetch(`${API_BASE}/api/coach`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            correction,
            drifted_context: coachContext.trim() || undefined,
          }),
        });
        const data = (await res.json()) as { status: string; message?: string };
        if (res.ok && data.status === "ok") {
          setCoachSuccess(data.message ?? "SOP added to agent memory.");
          setCoachCorrection("");
          setCoachContext("");
        } else {
          setCoachError(data.message ?? "Failed to add SOP");
        }
      } catch {
        setCoachError("Failed to submit coaching");
      } finally {
        setCoachSubmitting(false);
      }
    },
    [coachCorrection, coachContext, coachSubmitting]
  );

  if (loading && !drift) {
    return (
      <div className="flex h-screen flex-col bg-[#050508] text-zinc-100">
        <header className="border-b border-[#1f1f24] px-6 py-4 bg-black/30">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              ← Control Dashboard
            </Link>
          </div>
          <h1 className="text-xl font-semibold tracking-wide bg-gradient-to-r from-red-600 via-amber-600 to-violet-500 bg-clip-text text-transparent font-[family-name:var(--font-orbitron)] mt-2">
            AGENT MANAGER – BEHAVIORAL DRIFT
          </h1>
          <p className="text-xs text-zinc-500 mt-1">
            Monitor latency, token usage, tool redundancy, and reasoning coherence
          </p>
        </header>
        <div className="flex-1 flex items-center justify-center p-6">
          <p className="text-zinc-500">Loading drift metrics...</p>
        </div>
      </div>
    );
  }

  const coherence = drift?.reasoning_coherence ?? {
    evaluator_pass_rate_pct: 0,
    sessions_with_retries: 0,
    total_sessions: 0,
  };
  const toolUsage = drift?.redundant_tool_usage ?? {
    avg_tool_calls_per_coder_run: 0,
    max_tool_calls_in_run: 0,
    coder_runs_with_tool_data: 0,
  };

  const passRateStatus: "good" | "warn" | "bad" =
    coherence.evaluator_pass_rate_pct >= 80
      ? "good"
      : coherence.evaluator_pass_rate_pct >= 50
        ? "warn"
        : "bad";

  const toolStatus: "good" | "warn" | "bad" =
    toolUsage.avg_tool_calls_per_coder_run <= 8
      ? "good"
      : toolUsage.avg_tool_calls_per_coder_run <= 15
        ? "warn"
        : "bad";

  return (
    <div className="flex min-h-screen flex-col bg-[#050508] text-zinc-100 relative overflow-hidden">
      <div className="absolute top-0 right-0 w-64 h-64 opacity-[0.04] pointer-events-none bg-gradient-to-bl from-violet-500 to-transparent" />
      <div className="absolute bottom-0 left-0 w-48 h-48 opacity-[0.03] pointer-events-none bg-gradient-to-tr from-amber-600 to-transparent" />
      <header className="relative border-b border-[#1f1f24] px-6 py-4 bg-black/30">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            ← Control Dashboard
          </Link>
          <button
            onClick={fetchDrift}
            disabled={loading}
            className="text-sm text-violet-400 hover:text-violet-300 disabled:opacity-50"
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        <h1 className="text-xl font-semibold tracking-wide bg-gradient-to-r from-red-600 via-amber-600 to-violet-500 bg-clip-text text-transparent font-[family-name:var(--font-orbitron)] mt-2">
          AGENT MANAGER – BEHAVIORAL DRIFT
        </h1>
        <p className="text-xs text-zinc-500 mt-1 flex items-center gap-1.5">
          <span className="text-[10px] text-violet-500/80">⚡</span>
          Monitor latency, token usage, tool redundancy, and reasoning coherence
          across sessions
        </p>
      </header>

      <main className="relative flex-1 p-6 space-y-8">
        {/* System readiness panel */}
        <section className="rounded-lg border border-[#1f1f24] bg-zinc-900/30 p-4">
          <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3">
            System readiness
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className={`rounded border px-3 py-2 ${backendUnreachable ? "border-red-500/50 bg-red-500/10" : "border-emerald-500/30 bg-emerald-500/5"}`}>
              <p className="text-xs text-zinc-500">Backend</p>
              <p className={`text-sm font-medium ${backendUnreachable ? "text-red-400" : "text-emerald-400"}`}>
                {backendUnreachable ? "Unreachable" : (health?.backend ?? "—")}
              </p>
              {backendUnreachable && <p className="mt-1 text-xs text-zinc-400">cd backend && python3 -m uvicorn app.main:app --reload</p>}
            </div>
            <div className={`rounded border px-3 py-2 ${health && !health.ollama.ok ? "border-amber-500/50 bg-amber-500/10" : "border-emerald-500/30 bg-emerald-500/5"}`}>
              <p className="text-xs text-zinc-500">Ollama</p>
              <p className={`text-sm font-medium ${health && !health.ollama.ok ? "text-amber-400" : "text-emerald-400"}`}>
                {health?.ollama?.ok ? "OK" : (health ? "Not running" : "—")}
              </p>
              {health && !health.ollama.ok && <p className="mt-1 text-xs text-zinc-400">ollama serve; ollama pull qwen2.5-coder</p>}
            </div>
            <div className={`rounded border px-3 py-2 ${health && !health.docker?.ok ? "border-amber-500/50 bg-amber-500/10" : "border-emerald-500/30 bg-emerald-500/5"}`}>
              <p className="text-xs text-zinc-500">Docker / Sandbox</p>
              <p className={`text-sm font-medium ${health && !health.docker?.ok ? "text-amber-400" : "text-emerald-400"}`}>
                {health?.docker?.ok ? "OK" : (health ? "Not ready" : "—")}
              </p>
              {health && !health.docker?.ok && <p className="mt-1 text-xs text-zinc-400">.\build_sandbox.ps1</p>}
            </div>
            <div className={`rounded border px-3 py-2 ${health?.langsmith?.warning ? "border-amber-500/40 bg-amber-500/5" : "border-emerald-500/30 bg-emerald-500/5"}`}>
              <p className="text-xs text-zinc-500">LangSmith</p>
              <p className={`text-sm font-medium ${health?.langsmith?.warning ? "text-amber-400" : "text-emerald-400"}`}>
                {health?.langsmith?.warning ? "API key missing" : "OK"}
              </p>
              {health?.langsmith?.warning && <p className="mt-1 text-xs text-zinc-400"><Link href="/" className="text-violet-400 hover:underline">See config options</Link></p>}
            </div>
          </div>
          {health?.langsmith?.warning && (
            <div className="mt-3 rounded border border-amber-500/40 bg-amber-500/5 px-3 py-2">
              <p className="text-xs font-medium text-amber-400">LangSmith: Option A</p>
              <p className="text-xs text-zinc-400">Set LANGCHAIN_API_KEY in backend/.env (see backend/.env.example)</p>
              <p className="text-xs font-medium text-amber-400 mt-1">Option B</p>
              <p className="text-xs text-zinc-400">Set LANGCHAIN_TRACING_V2=false in backend/.env</p>
            </div>
          )}
        </section>

        {/* Coach Agent: flag drifted response, add correction as SOP */}
        <section className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-4">
          <h2 className="text-sm font-medium text-violet-300 uppercase tracking-wider mb-3">
            Coach Agent
          </h2>
          <p className="text-xs text-zinc-400 mb-4">
            Flag a drifted response and add a correction as a new SOP. The Coordinator will
            retrieve this guidance for future routing and planning.
          </p>
          <form onSubmit={handleCoachSubmit} className="space-y-3">
            <div>
              <label className="block text-xs text-zinc-500 mb-1">
                Drifted response / context (optional)
              </label>
              <textarea
                value={coachContext}
                onChange={(e) => setCoachContext(e.target.value)}
                placeholder="What did the agent do wrong? e.g. 'Used sync I/O instead of async'"
                rows={2}
                className="w-full rounded-lg border border-[#1f1f24] bg-zinc-900/80 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-500 mb-1">
                Correction (SOP) <span className="text-red-400">*</span>
              </label>
              <textarea
                value={coachCorrection}
                onChange={(e) => setCoachCorrection(e.target.value)}
                placeholder="The new standard to remember. e.g. 'Always use async/await for file I/O operations'"
                rows={3}
                required
                className="w-full rounded-lg border border-[#1f1f24] bg-zinc-900/80 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
              />
            </div>
            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={!coachCorrection.trim() || coachSubmitting}
                className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {coachSubmitting ? "Adding…" : "Add SOP to memory"}
              </button>
              {coachSuccess && (
                <span className="text-sm text-emerald-400">{coachSuccess}</span>
              )}
              {coachError && (
                <span className="text-sm text-red-400">{coachError}</span>
              )}
            </div>
          </form>
        </section>

        {error && (
          <div className="rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-3">
            <p className="font-medium text-red-400">Error loading drift data</p>
            <p className="mt-1 text-sm text-zinc-300">{error}</p>
          </div>
        )}

        {drift?.error && (
          <div className="rounded-lg border border-amber-500/50 bg-amber-500/10 px-4 py-3">
            <p className="font-medium text-amber-400">Warning</p>
            <p className="mt-1 text-sm text-zinc-300">{drift.error}</p>
          </div>
        )}

        {/* Summary metrics */}
        <section>
          <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3">
            Drift indicators
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Reasoning coherence (pass rate)"
              value={`${coherence.evaluator_pass_rate_pct}%`}
              subtext={`${coherence.sessions_with_retries} of ${coherence.total_sessions} sessions had retries`}
              status={passRateStatus}
            />
            <MetricCard
              title="Avg tool calls / coder run"
              value={toolUsage.avg_tool_calls_per_coder_run.toFixed(1)}
              subtext={`Max: ${toolUsage.max_tool_calls_in_run} (${toolUsage.coder_runs_with_tool_data} runs)`}
              status={toolStatus}
            />
            <MetricCard
              title="Entries analyzed"
              value={drift?.entries_analyzed ?? 0}
              subtext="Node end events from exegol.log"
            />
            <MetricCard
              title="Total sessions"
              value={coherence.total_sessions}
              subtext="Unique thread_ids with completed nodes"
            />
          </div>
        </section>

        {/* Latency by node */}
        <section>
          <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3">
            Latency degradation (by node)
          </h2>
          <div className="rounded-lg border border-[#1f1f24] bg-zinc-900/30 overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[#1f1f24]">
                  <th className="px-4 py-3 text-zinc-400 font-medium">Node</th>
                  <th className="px-4 py-3 text-zinc-400 font-medium">Avg (s)</th>
                  <th className="px-4 py-3 text-zinc-400 font-medium">P50 (s)</th>
                  <th className="px-4 py-3 text-zinc-400 font-medium">P95 (s)</th>
                  <th className="px-4 py-3 text-zinc-400 font-medium">Count</th>
                </tr>
              </thead>
              <tbody>
                {drift?.latency_by_node &&
                Object.keys(drift.latency_by_node).length > 0 ? (
                  Object.entries(drift.latency_by_node).map(([node, stats]) => (
                    <tr
                      key={node}
                      className="border-b border-[#1f1f24]/50 hover:bg-zinc-800/30"
                    >
                      <td className="px-4 py-3 font-medium text-zinc-200">
                        {NODE_LABELS[node] ?? node}
                      </td>
                      <td className="px-4 py-3 text-zinc-300">
                        {stats.avg_sec.toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-zinc-300">
                        {stats.p50_sec.toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-zinc-300">
                        {stats.p95_sec.toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-zinc-400">{stats.count}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-zinc-500">
                      No latency data yet. Run some graph executions to see metrics.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Token usage by node */}
        <section>
          <h2 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3">
            Token usage trends
          </h2>
          <div className="rounded-lg border border-[#1f1f24] bg-zinc-900/30 overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[#1f1f24]">
                  <th className="px-4 py-3 text-zinc-400 font-medium">Node</th>
                  <th className="px-4 py-3 text-zinc-400 font-medium">Avg tokens</th>
                  <th className="px-4 py-3 text-zinc-400 font-medium">Total</th>
                  <th className="px-4 py-3 text-zinc-400 font-medium">Runs</th>
                </tr>
              </thead>
              <tbody>
                {drift?.token_usage_by_node &&
                Object.keys(drift.token_usage_by_node).length > 0 ? (
                  Object.entries(drift.token_usage_by_node).map(
                    ([node, stats]) => (
                      <tr
                        key={node}
                        className="border-b border-[#1f1f24]/50 hover:bg-zinc-800/30"
                      >
                        <td className="px-4 py-3 font-medium text-zinc-200">
                          {NODE_LABELS[node] ?? node}
                        </td>
                        <td className="px-4 py-3 text-zinc-300">
                          {Math.round(stats.avg_tokens)}
                        </td>
                        <td className="px-4 py-3 text-zinc-300">
                          {stats.total_tokens}
                        </td>
                        <td className="px-4 py-3 text-zinc-400">{stats.count}</td>
                      </tr>
                    )
                  )
                ) : (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-zinc-500">
                      No token data yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}

export default function ManagerDashboard() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen flex-col bg-[#050508] items-center justify-center text-zinc-500">
          Loading…
        </div>
      }
    >
      <ManagerDashboardContent />
    </Suspense>
  );
}
