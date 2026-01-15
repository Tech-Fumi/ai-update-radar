"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface ExternalAiMeta {
  has_conversation: boolean;
  providers: string[];
  models: string[];
}

interface RunItem {
  run_id: string;
  trace_id: string | null;
  task_id: string;
  status: string;
  passed: boolean;
  duration_ms: number | null;
  changes: number | null;
  error_stage: string | null;
  error_code: string | null;
  output_preview: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  external_ai: ExternalAiMeta | null;
}

interface RunsResponse {
  runs: RunItem[];
  has_more: boolean;
  next_cursor: string | null;
}

interface StatsResponse {
  since: string;
  total: number;
  completed: number;
  failed: number;
  timeouts: number;
  by_error_stage: { error_stage: string; count: number }[];
  by_error_code: { error_code: string; count: number }[];
}

type StatusFilter = "all" | "completed" | "failed";
type ConversationFilter = "all" | "yes" | "no";

export default function RunsPage() {
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [traceIdFilter, setTraceIdFilter] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  // v0.1.7: 外部AIフィルタ
  const [conversationFilter, setConversationFilter] = useState<ConversationFilter>("all");
  const [providerFilter, setProviderFilter] = useState("");
  const [modelFilter, setModelFilter] = useState("");

  const fetchRuns = async (cursor?: string) => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.set("limit", "50");
      if (cursor) params.set("cursor", cursor);
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (traceIdFilter) params.set("trace_id", traceIdFilter);
      // v0.1.7: 外部AIフィルタ
      if (conversationFilter === "yes") params.set("has_conversation", "true");
      if (conversationFilter === "no") params.set("has_conversation", "false");
      if (providerFilter) params.set("provider", providerFilter);
      if (modelFilter) params.set("model", modelFilter);

      const response = await fetch(`/api/runs?${params.toString()}`);
      if (!response.ok) throw new Error("Failed to fetch runs");

      const data: RunsResponse = await response.json();

      if (cursor) {
        setRuns((prev) => [...prev, ...data.runs]);
      } else {
        setRuns(data.runs);
      }
      setHasMore(data.has_more);
      setNextCursor(data.next_cursor);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch("/api/runs/stats");
      if (response.ok) {
        const data: StatsResponse = await response.json();
        setStats(data);
      }
    } catch {
      // stats エラーは無視（メイン機能に影響しない）
    }
  };

  useEffect(() => {
    fetchRuns();
    fetchStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, conversationFilter]);

  const handleSearch = () => {
    fetchRuns();
  };

  const handleLoadMore = () => {
    if (nextCursor) fetchRuns(nextCursor);
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    const date = new Date(dateStr);
    return date.toLocaleString("ja-JP", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatDuration = (ms: number | null) => {
    if (ms === null) return "-";
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-6xl mx-auto px-4 py-12">
        {/* Header */}
        <header className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-3xl font-bold">Runs</h1>
            <Link
              href="/"
              className="text-slate-400 hover:text-slate-200 text-sm"
            >
              ← トップに戻る
            </Link>
          </div>

          {/* Stats Cards (24h) */}
          {stats && (
            <div className="grid grid-cols-3 gap-4 mb-6">
              {/* Failed Card */}
              <button
                onClick={() => setStatusFilter("failed")}
                className="bg-slate-900 border border-slate-800 rounded-lg p-4 hover:border-red-600 transition-colors text-left"
              >
                <p className="text-slate-400 text-xs mb-1">Failed (24h)</p>
                <p className="text-2xl font-bold text-red-400">{stats.failed}</p>
                <p className="text-slate-500 text-xs mt-1">
                  / {stats.total} total
                </p>
              </button>

              {/* Top error_stage Card */}
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                <p className="text-slate-400 text-xs mb-1">Top error_stage (24h)</p>
                {stats.by_error_stage.length > 0 ? (
                  <div className="space-y-1">
                    {stats.by_error_stage.slice(0, 3).map((item) => (
                      <div key={item.error_stage} className="flex justify-between items-center">
                        <span className="text-amber-400 text-sm">{item.error_stage}</span>
                        <span className="text-slate-300 text-sm font-mono">{item.count}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-500 text-sm">-</p>
                )}
              </div>

              {/* TIMEOUT Card */}
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                <p className="text-slate-400 text-xs mb-1">TIMEOUT (24h)</p>
                <p className="text-2xl font-bold text-orange-400">{stats.timeouts}</p>
                <p className="text-slate-500 text-xs mt-1">
                  {stats.failed > 0
                    ? `${Math.round((stats.timeouts / stats.failed) * 100)}% of failed`
                    : "-"}
                </p>
              </div>
            </div>
          )}

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-4">
            {/* Status Filter */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-sm">Status:</span>
              <div className="flex gap-1">
                {(["all", "completed", "failed"] as StatusFilter[]).map((s) => (
                  <button
                    key={s}
                    onClick={() => setStatusFilter(s)}
                    className={`px-3 py-1 rounded text-sm transition-colors ${
                      statusFilter === s
                        ? s === "failed"
                          ? "bg-red-600 text-white"
                          : s === "completed"
                          ? "bg-green-600 text-white"
                          : "bg-violet-600 text-white"
                        : "bg-slate-800 text-slate-400 hover:text-white"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Trace ID Filter */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-sm">trace_id:</span>
              <input
                type="text"
                value={traceIdFilter}
                onChange={(e) => setTraceIdFilter(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="部分一致検索"
                className="px-3 py-1 bg-slate-800 border border-slate-700 rounded text-sm text-white placeholder-slate-500 w-40"
              />
            </div>

            {/* v0.1.7: External AI Filters */}
            {/* Conversation Filter */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-sm">外部AI:</span>
              <div className="flex gap-1">
                {(["all", "yes", "no"] as ConversationFilter[]).map((c) => (
                  <button
                    key={c}
                    onClick={() => setConversationFilter(c)}
                    className={`px-3 py-1 rounded text-sm transition-colors ${
                      conversationFilter === c
                        ? c === "yes"
                          ? "bg-cyan-600 text-white"
                          : c === "no"
                          ? "bg-slate-600 text-white"
                          : "bg-violet-600 text-white"
                        : "bg-slate-800 text-slate-400 hover:text-white"
                    }`}
                  >
                    {c === "all" ? "all" : c === "yes" ? "有り" : "無し"}
                  </button>
                ))}
              </div>
            </div>

            {/* Provider Filter */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-sm">provider:</span>
              <input
                type="text"
                value={providerFilter}
                onChange={(e) => setProviderFilter(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="openai..."
                className="px-3 py-1 bg-slate-800 border border-slate-700 rounded text-sm text-white placeholder-slate-500 w-28"
              />
            </div>

            {/* Model Filter */}
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-sm">model:</span>
              <input
                type="text"
                value={modelFilter}
                onChange={(e) => setModelFilter(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="gpt-4..."
                className="px-3 py-1 bg-slate-800 border border-slate-700 rounded text-sm text-white placeholder-slate-500 w-28"
              />
            </div>

            <button
              onClick={handleSearch}
              className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-sm"
            >
              検索
            </button>
          </div>
        </header>

        {/* Error */}
        {error && (
          <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 mb-6">
            <p className="text-red-300">{error}</p>
          </div>
        )}

        {/* Table */}
        <div className="bg-slate-900 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-800">
              <tr>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">completed_at</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">status</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">duration</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">changes</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">外部AI</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">trace_id</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">error</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.run_id}
                  className="border-t border-slate-800 hover:bg-slate-800/50 cursor-pointer"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/runs/${run.run_id}`}
                      className="text-violet-400 hover:text-violet-300"
                    >
                      {formatDate(run.completed_at)}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        run.status === "completed"
                          ? "bg-green-900 text-green-300"
                          : "bg-red-900 text-red-300"
                      }`}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-300">
                    {formatDuration(run.duration_ms)}
                  </td>
                  <td className="px-4 py-3 text-slate-300">
                    {run.changes ?? "-"}
                  </td>
                  <td className="px-4 py-3">
                    {run.external_ai?.has_conversation ? (
                      <span
                        className="px-2 py-0.5 rounded text-xs font-medium bg-cyan-900 text-cyan-300"
                        title={`${run.external_ai.providers.join(", ")} / ${run.external_ai.models.join(", ")}`}
                      >
                        {run.external_ai.providers.length > 0
                          ? run.external_ai.providers.join(",")
                          : "AI"}
                      </span>
                    ) : (
                      <span className="text-slate-600 text-xs">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-500 font-mono text-xs">
                    {run.trace_id || "-"}
                  </td>
                  <td className="px-4 py-3">
                    {run.error_stage && (
                      <span className="text-red-400 text-xs">
                        {run.error_stage}
                        {run.error_code && `: ${run.error_code}`}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {runs.length === 0 && !loading && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                    データがありません
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Loading / Load More */}
        <div className="mt-6 text-center">
          {loading && <p className="text-slate-400">読み込み中...</p>}
          {!loading && hasMore && (
            <button
              onClick={handleLoadMore}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded text-sm"
            >
              もっと読み込む
            </button>
          )}
        </div>
      </div>
    </main>
  );
}
