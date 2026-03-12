"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

export default function ManagerDashboard() {
  const [drift, setDrift] = useState<DriftResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    fetchDrift();
    const t = setInterval(fetchDrift, 30000);
    return () => clearInterval(t);
  }, [fetchDrift]);

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
          <h1 className="text-xl font-semibold tracking-tight bg-gradient-to-r from-red-600 via-amber-600 to-violet-500 bg-clip-text text-transparent mt-2">
            Agent Manager – Behavioral Drift
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
    <div className="flex min-h-screen flex-col bg-[#050508] text-zinc-100">
      <header className="border-b border-[#1f1f24] px-6 py-4 bg-black/30">
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
        <h1 className="text-xl font-semibold tracking-tight bg-gradient-to-r from-red-600 via-amber-600 to-violet-500 bg-clip-text text-transparent mt-2">
          Agent Manager – Behavioral Drift
        </h1>
        <p className="text-xs text-zinc-500 mt-1">
          Monitor latency, token usage, tool redundancy, and reasoning coherence
          across sessions
        </p>
      </header>

      <main className="flex-1 p-6 space-y-8">
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
