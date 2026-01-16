"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

interface ConversationMeta {
  model?: string;
  tokens_in?: number;
  tokens_out?: number;
  [key: string]: unknown;
}

interface ConversationEntry {
  ts: string;
  role: string;
  source: string;
  content?: string;
  event?: string;
  meta?: ConversationMeta;
}

interface EvidenceLink {
  artifact: string;
  line_from?: number;
  line_to?: number;
  note?: string;
}

interface SummaryCard {
  decision: string;
  hypothesis: string;
  confidence: number;
  key_points: string[];
  evidence: string[];
  evidence_links?: EvidenceLink[];
  generated_by?: string;
  recommendation?: "retry" | "rerun" | "fix" | "noop";
}

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
    conversation_path?: string;
  };
  artifact_hashes?: Record<string, string>;
  created_at: string;
  started_at: string | null;
  completed_at: string;
  summary_card?: SummaryCard;
}

export default function RunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const run_id = params.run_id as string;

  const [run, setRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState(false);
  const [rerunError, setRerunError] = useState<string | null>(null);
  const [creatingFixTask, setCreatingFixTask] = useState(false);
  const [fixTaskResult, setFixTaskResult] = useState<{ task_id: string; trace_id: string } | null>(null);

  // Artifact content
  const [diffContent, setDiffContent] = useState<string | null>(null);
  const [stdoutContent, setStdoutContent] = useState<string | null>(null);
  const [stderrContent, setStderrContent] = useState<string | null>(null);
  const [conversationEntries, setConversationEntries] = useState<ConversationEntry[] | null>(null);

  // Collapsed state
  const [showOutput, setShowOutput] = useState(false);
  const [showDiff, setShowDiff] = useState(true);
  const [showStdout, setShowStdout] = useState(false);
  const [showStderr, setShowStderr] = useState(false);
  const [showConversation, setShowConversation] = useState(false);

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
        if (data.artifacts.conversation_path) {
          fetch(`/api/runs/${run_id}/artifacts/conversation.jsonl`)
            .then((r) => r.text())
            .then((text) => {
              const entries = text
                .split("\n")
                .filter((line) => line.trim())
                .map((line) => JSON.parse(line) as ConversationEntry);
              setConversationEntries(entries);
            })
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

  const handleRerun = async () => {
    setRerunning(true);
    setRerunError(null);
    try {
      const response = await fetch(`/api/runs/${run_id}/rerun`, {
        method: "POST",
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to rerun");
      }
      const data = await response.json();
      // 新しい run へ遷移（task_id から）
      // 注: run_id は非同期で生成されるため、一旦 runs 一覧へ
      router.push(`/runs?trace_id=${encodeURIComponent(data.trace_id)}`);
    } catch (err) {
      setRerunError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setRerunning(false);
    }
  };

  const handleFixTask = async () => {
    setCreatingFixTask(true);
    setFixTaskResult(null);
    try {
      const response = await fetch(`/api/runs/${run_id}/fix-task`, {
        method: "POST",
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to create fix task");
      }
      const data = await response.json();
      setFixTaskResult({ task_id: data.task_id, trace_id: data.trace_id });
    } catch (err) {
      setRerunError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setCreatingFixTask(false);
    }
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

          {/* Actions */}
          <div className="mt-6 flex items-center gap-3">
            {/* Retry: failed のときだけ */}
            {!run.summary.passed && (
              <button
                onClick={handleRerun}
                disabled={rerunning}
                className={`px-4 py-2 bg-red-600 hover:bg-red-500 disabled:bg-red-800 disabled:cursor-not-allowed rounded text-sm font-medium transition-colors ${
                  run.summary_card?.recommendation === "retry" ? "ring-2 ring-yellow-400 ring-offset-2 ring-offset-slate-950" : ""
                }`}
              >
                {rerunning ? "Retrying..." : "Retry"}
                {run.summary_card?.recommendation === "retry" && <span className="ml-1 text-yellow-300">★</span>}
              </button>
            )}
            {/* Re-run: 常時 */}
            <button
              onClick={handleRerun}
              disabled={rerunning}
              className={`px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:bg-violet-800 disabled:cursor-not-allowed rounded text-sm font-medium transition-colors ${
                run.summary_card?.recommendation === "rerun" ? "ring-2 ring-yellow-400 ring-offset-2 ring-offset-slate-950" : ""
              }`}
            >
              {rerunning ? "Re-running..." : "Re-run"}
              {run.summary_card?.recommendation === "rerun" && <span className="ml-1 text-yellow-300">★</span>}
            </button>
            {/* Fix Task: failed のときだけ */}
            {!run.summary.passed && (
              <button
                onClick={handleFixTask}
                disabled={creatingFixTask}
                className={`px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:bg-amber-800 disabled:cursor-not-allowed rounded text-sm font-medium transition-colors ${
                  run.summary_card?.recommendation === "fix" ? "ring-2 ring-yellow-400 ring-offset-2 ring-offset-slate-950" : ""
                }`}
              >
                {creatingFixTask ? "Creating..." : "Fix Task"}
                {run.summary_card?.recommendation === "fix" && <span className="ml-1 text-yellow-300">★</span>}
              </button>
            )}
          </div>

          {/* Fix Task Result */}
          {fixTaskResult && (
            <div className="mt-3 p-3 bg-green-900/30 border border-green-800 rounded">
              <p className="text-green-300 text-sm">
                Fix Task 作成完了: <span className="font-mono">{fixTaskResult.task_id}</span>
              </p>
              <p className="text-green-400 text-xs mt-1">
                trace_id: <span className="font-mono">{fixTaskResult.trace_id}</span>
              </p>
            </div>
          )}

          {/* Rerun Error */}
          {rerunError && (
            <div className="mt-3 p-2 bg-red-900/30 border border-red-800 rounded">
              <p className="text-red-300 text-sm">{rerunError}</p>
            </div>
          )}
        </section>

        {/* Summary Card (v0.1.9) */}
        {run.summary_card && (
          <section className="bg-slate-900 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <span className="text-amber-400">📋</span>
              Summary Card
              {run.summary_card.generated_by && (
                <span className="text-xs text-slate-500 font-normal">
                  ({run.summary_card.generated_by})
                </span>
              )}
            </h2>
            <div className="space-y-4">
              {/* Decision & Confidence & Recommendation */}
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <p className="text-slate-400 text-sm">Decision</p>
                  <p className={`text-lg font-semibold ${
                    run.summary_card.decision === "completed" || run.summary_card.decision === "成功"
                      ? "text-green-400"
                      : run.summary_card.decision === "failed" || run.summary_card.decision === "失敗"
                      ? "text-red-400"
                      : run.summary_card.decision.includes("再試行") || run.summary_card.decision === "Retry recommended"
                      ? "text-amber-400"
                      : "text-slate-300"
                  }`}>
                    {run.summary_card.decision}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400 text-sm">Confidence</p>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-2 bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-violet-500"
                        style={{ width: `${run.summary_card.confidence * 100}%` }}
                      />
                    </div>
                    <span className="text-sm text-slate-300">
                      {(run.summary_card.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                {/* Recommendation (v0.2.3) */}
                {run.summary_card.recommendation && run.summary_card.recommendation !== "noop" && (
                  <div>
                    <p className="text-slate-400 text-sm">Recommended</p>
                    <span className={`inline-flex items-center px-2 py-1 rounded text-sm font-medium ${
                      run.summary_card.recommendation === "retry" ? "bg-red-900/50 text-red-300 border border-red-700" :
                      run.summary_card.recommendation === "rerun" ? "bg-violet-900/50 text-violet-300 border border-violet-700" :
                      run.summary_card.recommendation === "fix" ? "bg-amber-900/50 text-amber-300 border border-amber-700" :
                      "bg-slate-700 text-slate-300"
                    }`}>
                      ★ {run.summary_card.recommendation.toUpperCase()}
                    </span>
                  </div>
                )}
              </div>

              {/* Hypothesis */}
              <div>
                <p className="text-slate-400 text-sm mb-1">Hypothesis</p>
                <p className="text-slate-200">{run.summary_card.hypothesis}</p>
              </div>

              {/* Key Points */}
              {run.summary_card.key_points.length > 0 && (
                <div>
                  <p className="text-slate-400 text-sm mb-2">Key Points</p>
                  <ul className="list-disc list-inside space-y-1">
                    {run.summary_card.key_points.map((point, idx) => (
                      <li key={idx} className="text-slate-300 text-sm">{point}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Evidence Links (v0.2.0) */}
              {run.summary_card.evidence_links && run.summary_card.evidence_links.length > 0 && (
                <div>
                  <p className="text-slate-400 text-sm mb-2">Evidence Links</p>
                  <ul className="space-y-2">
                    {run.summary_card.evidence_links.map((link, idx) => (
                      <li key={idx} className="bg-slate-800 rounded p-2">
                        <button
                          onClick={() => {
                            // Open the corresponding artifact section
                            if (link.artifact === "conversation.jsonl") setShowConversation(true);
                            else if (link.artifact === "stdout.log") setShowStdout(true);
                            else if (link.artifact === "stderr.log") setShowStderr(true);
                            else if (link.artifact === "patch.diff") setShowDiff(true);
                          }}
                          className="text-violet-400 hover:text-violet-300 text-sm font-mono"
                        >
                          {link.artifact}
                          {link.line_from && (
                            <span className="text-slate-500">
                              :L{link.line_from}
                              {link.line_to && link.line_to !== link.line_from && `-${link.line_to}`}
                            </span>
                          )}
                        </button>
                        {link.note && (
                          <p className="text-slate-400 text-xs mt-1">{link.note}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Evidence (legacy) */}
              {run.summary_card.evidence.length > 0 && !run.summary_card.evidence_links?.length && (
                <div>
                  <p className="text-slate-400 text-sm mb-2">Evidence</p>
                  <ul className="space-y-1">
                    {run.summary_card.evidence.map((ev, idx) => (
                      <li key={idx} className="text-slate-500 text-xs font-mono bg-slate-800 px-2 py-1 rounded">
                        {ev}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </section>
        )}

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

          {/* Conversation */}
          {run.artifacts.conversation_path && (
            <div className="bg-slate-900 rounded-lg">
              <button
                onClick={() => setShowConversation(!showConversation)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-800/50 rounded-t-lg"
              >
                <div className="flex items-center gap-3">
                  <span className="text-amber-400">conversation.jsonl</span>
                  <a
                    href={`/api/runs/${run_id}/artifacts/conversation.jsonl`}
                    download
                    className="text-xs text-slate-500 hover:text-slate-300"
                    onClick={(e) => e.stopPropagation()}
                  >
                    [download]
                  </a>
                </div>
                <span className="text-slate-400">{showConversation ? "▼" : "▶"}</span>
              </button>
              {showConversation && conversationEntries && (
                <div className="px-6 pb-6 space-y-3">
                  {conversationEntries.map((entry, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded ${
                        entry.role === "user"
                          ? "bg-blue-900/30 border-l-2 border-blue-500"
                          : entry.role === "assistant"
                          ? "bg-green-900/30 border-l-2 border-green-500"
                          : "bg-slate-800/50 border-l-2 border-slate-600"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className={`text-xs font-semibold ${
                            entry.role === "user"
                              ? "text-blue-400"
                              : entry.role === "assistant"
                              ? "text-green-400"
                              : "text-slate-400"
                          }`}
                        >
                          {entry.role}
                        </span>
                        <span className="text-xs text-slate-500">
                          {entry.source}
                        </span>
                        {entry.event && (
                          <span className="text-xs text-amber-500">
                            [{entry.event}]
                          </span>
                        )}
                        <span className="text-xs text-slate-600 ml-auto">
                          {new Date(entry.ts).toLocaleTimeString("ja-JP")}
                        </span>
                      </div>
                      {entry.content && (
                        <pre className="text-sm text-slate-300 whitespace-pre-wrap">
                          {entry.content}
                        </pre>
                      )}
                      {entry.meta && Object.keys(entry.meta).length > 0 && (
                        <div className="mt-2 text-xs text-slate-500">
                          {entry.meta.model && <span>model: {String(entry.meta.model)}</span>}
                          {entry.meta.tokens_in !== undefined && (
                            <span className="ml-2">in: {String(entry.meta.tokens_in)}</span>
                          )}
                          {entry.meta.tokens_out !== undefined && (
                            <span className="ml-2">out: {String(entry.meta.tokens_out)}</span>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
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
