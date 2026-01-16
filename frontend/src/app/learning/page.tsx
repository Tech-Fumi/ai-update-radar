"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface ReasonStats {
  total: number;
  accepted: number;
  rate: number;
}

interface MismatchEntry {
  run_id: string;
  recommended: string;
  reason: string;
  chosen: string;
  ts: string;
}

interface LearningStats {
  period_days: number;
  total_actions: number;
  acceptance_rate: number;
  by_recommended: Record<string, ReasonStats>;
  by_reason: Record<string, ReasonStats>;
  by_error_code: Record<string, ReasonStats>;
  confusion_matrix: Record<string, Record<string, number>>;
  mismatch_top: MismatchEntry[];
}

export default function LearningDashboard() {
  const [stats, setStats] = useState<LearningStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<"24h" | "7d">("7d");

  useEffect(() => {
    const fetchStats = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/learning/stats?since=${period}`);
        if (!response.ok) {
          throw new Error("Failed to fetch stats");
        }
        const data = await response.json();
        setStats(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, [period]);

  const formatRate = (rate: number) => `${(rate * 100).toFixed(1)}%`;

  const getRateColor = (rate: number) => {
    if (rate >= 0.8) return "text-green-400";
    if (rate >= 0.5) return "text-yellow-400";
    return "text-red-400";
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100">
        <div className="max-w-6xl mx-auto px-4 py-12">
          <p className="text-slate-400">Loading...</p>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100">
        <div className="max-w-6xl mx-auto px-4 py-12">
          <p className="text-red-400">{error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-6xl mx-auto px-4 py-12">
        {/* Header */}
        <header className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Rule Tuning Dashboard</h1>
            <p className="text-slate-400 text-sm mt-1">
              推奨ルールの改善ターゲットを特定
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPeriod("24h")}
              className={`px-3 py-1 rounded text-sm ${
                period === "24h"
                  ? "bg-violet-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:bg-slate-700"
              }`}
            >
              24h
            </button>
            <button
              onClick={() => setPeriod("7d")}
              className={`px-3 py-1 rounded text-sm ${
                period === "7d"
                  ? "bg-violet-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:bg-slate-700"
              }`}
            >
              7d
            </button>
          </div>
        </header>

        {stats && (
          <>
            {/* Overview */}
            <section className="grid grid-cols-3 gap-4 mb-8">
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                <p className="text-slate-400 text-sm">Total Actions</p>
                <p className="text-3xl font-bold">{stats.total_actions}</p>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                <p className="text-slate-400 text-sm">Acceptance Rate</p>
                <p className={`text-3xl font-bold ${getRateColor(stats.acceptance_rate)}`}>
                  {formatRate(stats.acceptance_rate)}
                </p>
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                <p className="text-slate-400 text-sm">Period</p>
                <p className="text-3xl font-bold">{stats.period_days}d</p>
              </div>
            </section>

            {/* By Reason (Rule ID) */}
            <section className="mb-8">
              <h2 className="text-lg font-semibold mb-4">Rule ID 別採用率</h2>
              <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-slate-800">
                    <tr>
                      <th className="px-4 py-2 text-left text-sm font-medium text-slate-400">Rule ID</th>
                      <th className="px-4 py-2 text-right text-sm font-medium text-slate-400">Total</th>
                      <th className="px-4 py-2 text-right text-sm font-medium text-slate-400">Accepted</th>
                      <th className="px-4 py-2 text-right text-sm font-medium text-slate-400">Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(stats.by_reason)
                      .sort((a, b) => b[1].total - a[1].total)
                      .map(([reason, data]) => (
                        <tr key={reason} className="border-t border-slate-800">
                          <td className="px-4 py-2 font-mono text-sm">{reason}</td>
                          <td className="px-4 py-2 text-right">{data.total}</td>
                          <td className="px-4 py-2 text-right">{data.accepted}</td>
                          <td className={`px-4 py-2 text-right font-semibold ${getRateColor(data.rate)}`}>
                            {formatRate(data.rate)}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* By Recommended */}
            <section className="mb-8">
              <h2 className="text-lg font-semibold mb-4">推奨アクション別採用率</h2>
              <div className="grid grid-cols-4 gap-4">
                {["retry", "rerun", "fix", "noop"].map((rec) => {
                  const data = stats.by_recommended[rec] || { total: 0, accepted: 0, rate: 0 };
                  return (
                    <div key={rec} className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                      <p className="text-slate-400 text-sm uppercase">{rec}</p>
                      <p className={`text-2xl font-bold ${getRateColor(data.rate)}`}>
                        {formatRate(data.rate)}
                      </p>
                      <p className="text-slate-500 text-xs">
                        {data.accepted}/{data.total}
                      </p>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* Confusion Matrix */}
            <section className="mb-8">
              <h2 className="text-lg font-semibold mb-4">Confusion Matrix（推奨 vs 選択）</h2>
              <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-slate-800">
                    <tr>
                      <th className="px-4 py-2 text-left text-sm font-medium text-slate-400">Recommended ↓ / Chosen →</th>
                      {["retry", "rerun", "fix"].map((cho) => (
                        <th key={cho} className="px-4 py-2 text-center text-sm font-medium text-slate-400 uppercase">
                          {cho}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {["retry", "rerun", "fix", "noop"].map((rec) => (
                      <tr key={rec} className="border-t border-slate-800">
                        <td className="px-4 py-2 font-medium uppercase">{rec}</td>
                        {["retry", "rerun", "fix"].map((cho) => {
                          const count = stats.confusion_matrix[rec]?.[cho] || 0;
                          const isMatch = rec === cho;
                          return (
                            <td
                              key={cho}
                              className={`px-4 py-2 text-center ${
                                isMatch
                                  ? "bg-green-900/30 text-green-300"
                                  : count > 0
                                  ? "bg-red-900/30 text-red-300"
                                  : "text-slate-600"
                              }`}
                            >
                              {count}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-slate-500 text-xs mt-2">
                緑: 推奨通り / 赤: ズレ
              </p>
            </section>

            {/* Mismatch Top */}
            <section className="mb-8">
              <h2 className="text-lg font-semibold mb-4">最近のズレ（推奨 ≠ 選択）</h2>
              {stats.mismatch_top.length === 0 ? (
                <p className="text-slate-500">ズレなし（全て推奨通り）</p>
              ) : (
                <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead className="bg-slate-800">
                      <tr>
                        <th className="px-4 py-2 text-left text-sm font-medium text-slate-400">Run ID</th>
                        <th className="px-4 py-2 text-left text-sm font-medium text-slate-400">Rule</th>
                        <th className="px-4 py-2 text-left text-sm font-medium text-slate-400">Recommended</th>
                        <th className="px-4 py-2 text-left text-sm font-medium text-slate-400">Chosen</th>
                        <th className="px-4 py-2 text-left text-sm font-medium text-slate-400">Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.mismatch_top.map((entry, i) => (
                        <tr key={i} className="border-t border-slate-800">
                          <td className="px-4 py-2">
                            <Link
                              href={`/runs/${entry.run_id}`}
                              className="font-mono text-sm text-violet-400 hover:text-violet-300"
                            >
                              {entry.run_id}
                            </Link>
                          </td>
                          <td className="px-4 py-2 font-mono text-sm text-slate-400">{entry.reason}</td>
                          <td className="px-4 py-2">
                            <span className="px-2 py-0.5 bg-slate-800 rounded text-sm uppercase">
                              {entry.recommended}
                            </span>
                          </td>
                          <td className="px-4 py-2">
                            <span className="px-2 py-0.5 bg-red-900/50 text-red-300 rounded text-sm uppercase">
                              {entry.chosen}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-slate-500 text-sm">
                            {new Date(entry.ts).toLocaleString("ja-JP")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Navigation */}
            <footer className="mt-12 pt-6 border-t border-slate-800">
              <Link href="/runs" className="text-violet-400 hover:text-violet-300 text-sm">
                ← Runs 一覧に戻る
              </Link>
            </footer>
          </>
        )}
      </div>
    </main>
  );
}
