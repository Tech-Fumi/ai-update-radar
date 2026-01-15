"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface CiFixRun {
  run_id: string;
  status: "DETECTED" | "IN_PROGRESS" | "DONE" | "UNKNOWN";
  issue: string | null;
  sha: string | null;
  workflow_name: string | null;
  project: string | null;
  t_start: number | null;
  t_fix: number | null;
  detected_at: string | null;
  started_at: string | null;
  done_at: string | null;
  updated_at: string | null;
}

interface CiFixResponse {
  runs: CiFixRun[];
  total: number;
  has_more: boolean;
}

type StatusFilter = "all" | "DETECTED" | "IN_PROGRESS" | "DONE";

export default function CiFixPage() {
  const [runs, setRuns] = useState<CiFixRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [total, setTotal] = useState(0);

  const fetchRuns = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.set("limit", "50");
      if (statusFilter !== "all") params.set("status", statusFilter);

      const response = await fetch(`/api/ci-fix/runs?${params.toString()}`);
      if (!response.ok) throw new Error("Failed to fetch runs");

      const data: CiFixResponse = await response.json();
      setRuns(data.runs);
      setTotal(data.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

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

  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return "-";
    if (seconds < 60) return `${seconds}s`;
    return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  };

  const statusColor = (status: string) => {
    switch (status) {
      case "DONE":
        return "bg-green-900 text-green-300";
      case "IN_PROGRESS":
        return "bg-yellow-900 text-yellow-300";
      case "DETECTED":
        return "bg-blue-900 text-blue-300";
      default:
        return "bg-slate-800 text-slate-400";
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-6xl mx-auto px-4 py-12">
        {/* Header */}
        <header className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-3xl font-bold">CI Fix (SLO)</h1>
            <Link
              href="/"
              className="text-slate-400 hover:text-slate-200 text-sm"
            >
              ← トップに戻る
            </Link>
          </div>
          <p className="text-slate-400 text-sm mb-4">
            CI 失敗 → AI Farm 自動修正のトラッキング
          </p>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-slate-400 text-sm">Status:</span>
              <div className="flex gap-1">
                {(["all", "DETECTED", "IN_PROGRESS", "DONE"] as StatusFilter[]).map((s) => (
                  <button
                    key={s}
                    onClick={() => setStatusFilter(s)}
                    className={`px-3 py-1 rounded text-sm transition-colors ${
                      statusFilter === s
                        ? s === "DONE"
                          ? "bg-green-600 text-white"
                          : s === "IN_PROGRESS"
                          ? "bg-yellow-600 text-white"
                          : s === "DETECTED"
                          ? "bg-blue-600 text-white"
                          : "bg-violet-600 text-white"
                        : "bg-slate-800 text-slate-400 hover:text-white"
                    }`}
                  >
                    {s === "all" ? "All" : s}
                  </button>
                ))}
              </div>
            </div>
            <span className="text-slate-500 text-sm">
              {total} runs
            </span>
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
                <th className="px-4 py-3 text-left text-slate-400 font-medium">run_id</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">status</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">t_start</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">t_fix</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">issue</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">workflow</th>
                <th className="px-4 py-3 text-left text-slate-400 font-medium">updated</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.run_id}
                  className="border-t border-slate-800 hover:bg-slate-800/50"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/ci-fix/${run.run_id}`}
                      className="text-violet-400 hover:text-violet-300 font-mono text-xs"
                    >
                      {run.run_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor(run.status)}`}>
                      {run.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-300 font-mono text-xs">
                    {formatDuration(run.t_start)}
                  </td>
                  <td className="px-4 py-3 text-slate-300 font-mono text-xs">
                    {formatDuration(run.t_fix)}
                  </td>
                  <td className="px-4 py-3">
                    {run.issue && (
                      <a
                        href={`https://github.com/Tech-Fumi/${run.project}/issues/${run.issue}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:text-blue-300 text-xs"
                      >
                        #{run.issue}
                      </a>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs truncate max-w-32">
                    {run.workflow_name || "-"}
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">
                    {formatDate(run.updated_at)}
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

        {/* Loading */}
        {loading && (
          <div className="mt-6 text-center">
            <p className="text-slate-400">読み込み中...</p>
          </div>
        )}
      </div>
    </main>
  );
}
