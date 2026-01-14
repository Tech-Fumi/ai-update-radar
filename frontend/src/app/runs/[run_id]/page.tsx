"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

interface RunDetail {
  task_id: string;
  trace_id: string;
  run_id: string;
  status: string;
  summary: {
    passed: boolean;
    duration_ms: number | null;
    changes: number | null;
    error_stage?: string;
    error_code?: string;
  };
  output: string;
  artifacts: {
    diff_path?: string;
    stdout_path?: string;
    stderr_path?: string;
  };
  artifact_hashes?: Record<string, string>;
  created_at: string;
  started_at: string | null;
  completed_at: string;
}

export default function RunDetailPage() {
  const params = useParams();
  const run_id = params.run_id as string;

  const [run, setRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Artifact content
  const [diffContent, setDiffContent] = useState<string | null>(null);
  const [stdoutContent, setStdoutContent] = useState<string | null>(null);
  const [stderrContent, setStderrContent] = useState<string | null>(null);

  // Collapsed state
  const [showOutput, setShowOutput] = useState(false);
  const [showDiff, setShowDiff] = useState(true);
  const [showStdout, setShowStdout] = useState(false);
  const [showStderr, setShowStderr] = useState(false);

  useEffect(() => {
    const fetchRun = async () => {
      try {
        const response = await fetch(`/api/runs/${run_id}`);
        if (!response.ok) throw new Error("Failed to fetch run");
        const data: RunDetail = await response.json();
        setRun(data);

        // Fetch artifacts
        if (data.artifacts.diff_path) {
          fetch(`/api/runs/${run_id}/artifacts/patch.diff`)
            .then((r) => r.text())
            .then(setDiffContent)
            .catch(() => {});
        }
        if (data.artifacts.stdout_path) {
          fetch(`/api/runs/${run_id}/artifacts/stdout.log`)
            .then((r) => r.text())
            .then(setStdoutContent)
            .catch(() => {});
        }
        if (data.artifacts.stderr_path) {
          fetch(`/api/runs/${run_id}/artifacts/stderr.log`)
            .then((r) => r.text())
            .then(setStderrContent)
            .catch(() => {});
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    if (run_id) fetchRun();
  }, [run_id]);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleString("ja-JP");
  };

  const formatDuration = (ms: number | null) => {
    if (ms === null) return "-";
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100">
        <div className="max-w-5xl mx-auto px-4 py-12">
          <p className="text-slate-400">読み込み中...</p>
        </div>
      </main>
    );
  }

  if (error || !run) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100">
        <div className="max-w-5xl mx-auto px-4 py-12">
          <p className="text-red-400">{error || "データが見つかりません"}</p>
          <Link
            href="/runs"
            className="text-violet-400 hover:text-violet-300 mt-4 inline-block"
          >
            ← Runs 一覧に戻る
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-5xl mx-auto px-4 py-12">
        {/* Header */}
        <header className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-2xl font-bold font-mono">{run.run_id}</h1>
            <Link
              href="/runs"
              className="text-slate-400 hover:text-slate-200 text-sm"
            >
              ← Runs 一覧に戻る
            </Link>
          </div>
          <p className="text-slate-400 text-sm">
            trace_id: <span className="font-mono">{run.trace_id}</span>
          </p>
        </header>

        {/* Summary Card */}
        <section className="bg-slate-900 rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Summary</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-slate-400 text-sm">Status</p>
              <span
                className={`inline-block px-2 py-0.5 rounded text-sm font-medium ${
                  run.summary.passed
                    ? "bg-green-900 text-green-300"
                    : "bg-red-900 text-red-300"
                }`}
              >
                {run.status}
              </span>
            </div>
            <div>
              <p className="text-slate-400 text-sm">Duration</p>
              <p className="text-white">{formatDuration(run.summary.duration_ms)}</p>
            </div>
            <div>
              <p className="text-slate-400 text-sm">Changes</p>
              <p className="text-white">{run.summary.changes ?? "-"}</p>
            </div>
            <div>
              <p className="text-slate-400 text-sm">Completed</p>
              <p className="text-white text-sm">{formatDate(run.completed_at)}</p>
            </div>
          </div>

          {/* Error info */}
          {run.summary.error_stage && (
            <div className="mt-4 p-3 bg-red-900/30 border border-red-800 rounded">
              <p className="text-red-300 text-sm">
                <span className="font-semibold">Error Stage:</span> {run.summary.error_stage}
                {run.summary.error_code && (
                  <span className="ml-4">
                    <span className="font-semibold">Code:</span> {run.summary.error_code}
                  </span>
                )}
              </p>
            </div>
          )}
        </section>

        {/* Output */}
        <section className="bg-slate-900 rounded-lg mb-6">
          <button
            onClick={() => setShowOutput(!showOutput)}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-800/50 rounded-t-lg"
          >
            <h2 className="text-lg font-semibold">Output</h2>
            <span className="text-slate-400">{showOutput ? "▼" : "▶"}</span>
          </button>
          {showOutput && (
            <div className="px-6 pb-6">
              <pre className="bg-slate-950 p-4 rounded text-sm text-slate-300 overflow-x-auto whitespace-pre-wrap">
                {run.output || "(empty)"}
              </pre>
            </div>
          )}
        </section>

        {/* Artifacts */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Artifacts</h2>

          {/* Diff */}
          {run.artifacts.diff_path && (
            <div className="bg-slate-900 rounded-lg">
              <button
                onClick={() => setShowDiff(!showDiff)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-800/50 rounded-t-lg"
              >
                <div className="flex items-center gap-3">
                  <span className="text-green-400">patch.diff</span>
                  <a
                    href={`/api/runs/${run_id}/artifacts/patch.diff`}
                    download
                    className="text-xs text-slate-500 hover:text-slate-300"
                    onClick={(e) => e.stopPropagation()}
                  >
                    [download]
                  </a>
                </div>
                <span className="text-slate-400">{showDiff ? "▼" : "▶"}</span>
              </button>
              {showDiff && diffContent && (
                <div className="px-6 pb-6">
                  <pre className="bg-slate-950 p-4 rounded text-sm text-slate-300 overflow-x-auto whitespace-pre">
                    {diffContent || "(empty)"}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Stdout */}
          {run.artifacts.stdout_path && (
            <div className="bg-slate-900 rounded-lg">
              <button
                onClick={() => setShowStdout(!showStdout)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-800/50 rounded-t-lg"
              >
                <div className="flex items-center gap-3">
                  <span className="text-blue-400">stdout.log</span>
                  <a
                    href={`/api/runs/${run_id}/artifacts/stdout.log`}
                    download
                    className="text-xs text-slate-500 hover:text-slate-300"
                    onClick={(e) => e.stopPropagation()}
                  >
                    [download]
                  </a>
                </div>
                <span className="text-slate-400">{showStdout ? "▼" : "▶"}</span>
              </button>
              {showStdout && (
                <div className="px-6 pb-6">
                  <pre className="bg-slate-950 p-4 rounded text-sm text-slate-300 overflow-x-auto whitespace-pre-wrap max-h-96 overflow-y-auto">
                    {stdoutContent || "(empty)"}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Stderr */}
          {run.artifacts.stderr_path && (
            <div className="bg-slate-900 rounded-lg">
              <button
                onClick={() => setShowStderr(!showStderr)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-800/50 rounded-t-lg"
              >
                <div className="flex items-center gap-3">
                  <span className="text-red-400">stderr.log</span>
                  <a
                    href={`/api/runs/${run_id}/artifacts/stderr.log`}
                    download
                    className="text-xs text-slate-500 hover:text-slate-300"
                    onClick={(e) => e.stopPropagation()}
                  >
                    [download]
                  </a>
                </div>
                <span className="text-slate-400">{showStderr ? "▼" : "▶"}</span>
              </button>
              {showStderr && (
                <div className="px-6 pb-6">
                  <pre className="bg-slate-950 p-4 rounded text-sm text-red-300 overflow-x-auto whitespace-pre-wrap max-h-96 overflow-y-auto">
                    {stderrContent || "(empty)"}
                  </pre>
                </div>
              )}
            </div>
          )}
        </section>

        {/* Integrity */}
        {run.artifact_hashes && Object.keys(run.artifact_hashes).length > 0 && (
          <section className="mt-6 bg-slate-900 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Integrity Hashes</h2>
            <div className="space-y-2">
              {Object.entries(run.artifact_hashes).map(([file, hash]) => (
                <div key={file} className="flex items-center gap-4 text-sm">
                  <span className="text-slate-400 w-24">{file}</span>
                  <code className="text-slate-500 font-mono text-xs break-all">
                    {hash}
                  </code>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
