"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

interface CiFixEvent {
  event_type: string;
  timestamp: string;
  agent: string | null;
  result: Record<string, unknown> | null;
}

interface CiFixRunDetail {
  run_id: string;
  status: "DETECTED" | "IN_PROGRESS" | "DONE" | "UNKNOWN";
  events: CiFixEvent[];
  t_start: number | null;
  t_fix: number | null;
  detected_at: string | null;
  started_at: string | null;
  done_at: string | null;
  issue: string | null;
  sha: string | null;
  workflow_name: string | null;
  project: string | null;
  run_url: string | null;
}

export default function CiFixRunDetailPage() {
  const params = useParams();
  const runId = params.run_id as string;

  const [run, setRun] = useState<CiFixRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchRun = async () => {
      try {
        setLoading(true);
        const response = await fetch(`/api/ci-fix/runs/${runId}`);
        if (!response.ok) {
          if (response.status === 404) {
            throw new Error("Run not found");
          }
          throw new Error("Failed to fetch run");
        }
        const data: CiFixRunDetail = await response.json();
        setRun(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    if (runId) fetchRun();
  }, [runId]);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    const date = new Date(dateStr);
    return date.toLocaleString("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
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

  const eventIcon = (eventType: string) => {
    switch (eventType) {
      case "DETECTED":
        return "🔍";
      case "FIX_STARTED":
        return "🤖";
      case "FIX_DONE":
        return "✅";
      default:
        return "📌";
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <p className="text-slate-400">読み込み中...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100">
        <div className="max-w-4xl mx-auto px-4 py-12">
          <div className="bg-red-900/50 border border-red-700 rounded-lg p-4">
            <p className="text-red-300">{error}</p>
          </div>
          <Link href="/ci-fix" className="text-violet-400 hover:text-violet-300 mt-4 inline-block">
            ← 一覧に戻る
          </Link>
        </div>
      </main>
    );
  }

  if (!run) return null;

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-4xl mx-auto px-4 py-12">
        {/* Header */}
        <header className="mb-8">
          <Link href="/ci-fix" className="text-slate-400 hover:text-slate-200 text-sm mb-4 inline-block">
            ← CI Fix 一覧
          </Link>
          <div className="flex items-center gap-4 mb-2">
            <h1 className="text-2xl font-bold font-mono">{run.run_id}</h1>
            <span className={`px-3 py-1 rounded text-sm font-medium ${statusColor(run.status)}`}>
              {run.status}
            </span>
          </div>
          {run.workflow_name && (
            <p className="text-slate-400">{run.workflow_name}</p>
          )}
        </header>

        {/* Metrics */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-slate-900 rounded-lg p-4">
            <p className="text-slate-400 text-sm mb-1">t_start</p>
            <p className="text-2xl font-mono">{formatDuration(run.t_start)}</p>
          </div>
          <div className="bg-slate-900 rounded-lg p-4">
            <p className="text-slate-400 text-sm mb-1">t_fix</p>
            <p className="text-2xl font-mono">{formatDuration(run.t_fix)}</p>
          </div>
          <div className="bg-slate-900 rounded-lg p-4">
            <p className="text-slate-400 text-sm mb-1">Issue</p>
            {run.issue ? (
              <a
                href={`https://github.com/Tech-Fumi/${run.project}/issues/${run.issue}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xl text-blue-400 hover:text-blue-300"
              >
                #{run.issue}
              </a>
            ) : (
              <p className="text-xl text-slate-500">-</p>
            )}
          </div>
          <div className="bg-slate-900 rounded-lg p-4">
            <p className="text-slate-400 text-sm mb-1">SHA</p>
            <p className="text-lg font-mono text-slate-300">{run.sha?.slice(0, 7) || "-"}</p>
          </div>
        </section>

        {/* Timeline */}
        <section className="mb-8">
          <h2 className="text-lg font-bold mb-4">Timeline</h2>
          <div className="bg-slate-900 rounded-lg p-4">
            <div className="space-y-4">
              {run.events.map((event, i) => (
                <div key={i} className="flex items-start gap-4">
                  <div className="text-2xl">{eventIcon(event.event_type)}</div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{event.event_type}</span>
                      {event.agent && (
                        <span className="text-xs bg-slate-800 px-2 py-0.5 rounded">
                          {event.agent}
                        </span>
                      )}
                    </div>
                    <p className="text-slate-400 text-sm">{formatDate(event.timestamp)}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Links */}
        <section>
          <h2 className="text-lg font-bold mb-4">Links</h2>
          <div className="flex gap-4">
            {run.issue && run.project && (
              <a
                href={`https://github.com/Tech-Fumi/${run.project}/issues/${run.issue}`}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded text-sm"
              >
                GitHub Issue
              </a>
            )}
            {run.run_url && (
              <a
                href={run.run_url}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded text-sm"
              >
                GitHub Actions Run
              </a>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
