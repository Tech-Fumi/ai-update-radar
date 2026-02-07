"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

interface Meaning {
  title: string;
  meaning: string;
  category?: "feature" | "fix" | "improvement" | "security" | "breaking";
}

// カテゴリ定義
const CATEGORY_CONFIG = {
  feature: { label: "🚀 新機能", order: 1, color: "text-emerald-400", border: "border-emerald-600" },
  fix: { label: "🐛 バグ修正", order: 2, color: "text-amber-400", border: "border-amber-600" },
  improvement: { label: "🔧 改善", order: 3, color: "text-blue-400", border: "border-blue-600" },
  security: { label: "🔒 セキュリティ", order: 4, color: "text-red-400", border: "border-red-600" },
  breaking: { label: "💥 破壊的変更", order: 5, color: "text-rose-400", border: "border-rose-600" },
} as const;

// Codex カテゴリ定義
const CODEX_CATEGORY_CONFIG = {
  feature: { label: "🚀 新機能", color: "text-emerald-400", bg: "bg-emerald-900/30" },
  fix: { label: "🐛 修正", color: "text-amber-400", bg: "bg-amber-900/30" },
  improvement: { label: "🔧 改善", color: "text-blue-400", bg: "bg-blue-900/30" },
  security: { label: "🔒 セキュリティ", color: "text-red-400", bg: "bg-red-900/30" },
  breaking: { label: "💥 破壊的変更", color: "text-rose-400", bg: "bg-rose-900/30" },
  other: { label: "📝 その他", color: "text-slate-400", bg: "bg-slate-800" },
} as const;

interface Release {
  version: string;
  date: string;
  link: string;
  highlights_en: string[];
  highlights_ja: string[];
  meanings?: Meaning[];
}

interface ReleasesData {
  updated_at: string;
  releases: Release[];
}

// Codex 用の型定義
interface CodexActionItem {
  task: string;
  source_feature: string;
  category: string;
}

interface CodexCategorizedHighlights {
  feature: string[];
  fix: string[];
  improvement: string[];
  security: string[];
  breaking: string[];
  other: string[];
}

interface CodexRelevance {
  applies_to_you?: boolean;
  reasons?: string[];
  affected_indices?: number[];
  opportunity_indices?: number[];
  opportunities?: Array<{ feature: string; benefit: string; projects?: string[] }>;
}

interface CodexRelease {
  version: string;
  date: string;
  link: string;
  highlights_en: string[];
  highlights_ja?: string[];
  categorized_highlights?: CodexCategorizedHighlights;
  action_items?: CodexActionItem[];
  relevance?: CodexRelevance;
  explanations?: Record<string, string>;
  prerelease: boolean;
}

interface CodexReleasesData {
  releases: CodexRelease[];
}

type ReleaseSource = "claude" | "codex";

// 送信結果の型
interface SubmitResult {
  success: boolean;
  message: string;
}

type RelayStatus = "checking" | "connected" | "disconnected";

export default function ReleasePage({
  params,
}: {
  params: Promise<{ version: string }>;
}) {
  const [version, setVersion] = useState<string>("");
  const [release, setRelease] = useState<Release | null>(null);
  const [codexRelease, setCodexRelease] = useState<CodexRelease | null>(null);
  const [source, setSource] = useState<ReleaseSource>("claude");
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  // 選択・送信機能用 state
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<SubmitResult | null>(null);
  const [relayStatus, setRelayStatus] = useState<RelayStatus>("checking");

  useEffect(() => {
    params.then((p) => setVersion(p.version));
  }, [params]);

  useEffect(() => {
    if (!version) return;

    // Codex のバージョンは "rust-" で始まる
    const isCodex = version.startsWith("rust-");
    setSource(isCodex ? "codex" : "claude");

    const cacheBust = `?t=${Date.now()}`;
    if (isCodex) {
      // Codex リリースを取得
      fetch(`/data/codex_releases.json${cacheBust}`)
        .then((res) => res.json())
        .then((data: CodexReleasesData) => {
          const found = data.releases.find((r) => r.version === version);
          if (found) {
            setCodexRelease(found);
          } else {
            setNotFound(true);
          }
          setLoading(false);
        })
        .catch((err) => {
          console.error("Failed to load Codex release:", err);
          setNotFound(true);
          setLoading(false);
        });
    } else {
      // Claude Code リリースを取得
      fetch(`/data/releases.json${cacheBust}`)
        .then((res) => res.json())
        .then((data: ReleasesData) => {
          const found = data.releases.find((r) => r.version === version);
          if (found) {
            setRelease(found);
          } else {
            setNotFound(true);
          }
          setLoading(false);
        })
        .catch((err) => {
          console.error("Failed to load release:", err);
          setNotFound(true);
          setLoading(false);
        });
    }
  }, [version]);

  // Relay API の接続確認
  useEffect(() => {
    const checkRelay = async () => {
      try {
        const res = await fetch("/api/submit-tasks");
        const data = await res.json();
        setRelayStatus(data.relay_api === "connected" ? "connected" : "disconnected");
      } catch {
        setRelayStatus("disconnected");
      }
    };
    checkRelay();
    const interval = setInterval(checkRelay, 30000);
    return () => clearInterval(interval);
  }, []);

  // アイテム選択のトグル
  const toggleItem = (key: string) => {
    const newSelected = new Set(selected);
    if (newSelected.has(key)) {
      newSelected.delete(key);
    } else {
      newSelected.add(key);
    }
    setSelected(newSelected);
  };

  // タスク送信
  const handleSubmit = async () => {
    if (selected.size === 0 || !codexRelease) return;

    setSubmitting(true);
    setSubmitResult(null);

    const relevance = codexRelease.relevance;
    const highlights = codexRelease.highlights_ja?.length ? codexRelease.highlights_ja : codexRelease.highlights_en;

    // 選択されたアイテムをタスクに変換
    const tasks: Array<{ task: string; source_feature: string; priority: number; project: string; category: string }> = [];

    selected.forEach((key) => {
      if (key.startsWith("affected-")) {
        const idx = parseInt(key.replace("affected-", ""), 10);
        const affectedIdx = relevance?.affected_indices?.[idx];
        if (affectedIdx !== undefined && highlights[affectedIdx]) {
          tasks.push({
            task: `確認: ${highlights[affectedIdx]}`,
            source_feature: `${codexRelease.version} 影響あり`,
            priority: tasks.length + 1,
            project: "MCP Codex",
            category: "tooling",
          });
        }
      } else if (key.startsWith("opportunity-")) {
        const idx = parseInt(key.replace("opportunity-", ""), 10);
        const opportunity = relevance?.opportunities?.[idx];
        if (opportunity) {
          tasks.push({
            task: `${opportunity.feature} を有効化: ${opportunity.benefit}`,
            source_feature: `${codexRelease.version} 機能提案`,
            priority: tasks.length + 1,
            project: opportunity.projects?.[0] || "infra-automation",
            category: "tooling",
          });
        }
      } else if (key.startsWith("action-")) {
        const idx = parseInt(key.replace("action-", ""), 10);
        const actionItem = codexRelease.action_items?.[idx];
        if (actionItem) {
          tasks.push({
            task: actionItem.task,
            source_feature: actionItem.source_feature,
            priority: tasks.length + 1,
            project: "MCP Codex",
            category: "tooling",
          });
        }
      }
    });

    if (tasks.length === 0) {
      setSubmitResult({ success: false, message: "送信するタスクがありません" });
      setSubmitting(false);
      return;
    }

    try {
      const res = await fetch("/api/submit-tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: tasks }),
      });
      const result = await res.json();

      if (result.success) {
        setSubmitResult({ success: true, message: `${tasks.length} 件のタスクを送信しました` });
        setSelected(new Set());
      } else {
        setSubmitResult({ success: false, message: result.message || "送信に失敗しました" });
      }
    } catch (err) {
      setSubmitResult({ success: false, message: "送信エラーが発生しました" });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100">
        <div className="max-w-4xl mx-auto px-4 py-12">
          <p className="text-slate-400">読み込み中...</p>
        </div>
      </main>
    );
  }

  if (notFound || (source === "claude" && !release) || (source === "codex" && !codexRelease)) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100">
        <div className="max-w-4xl mx-auto px-4 py-12">
          <Link
            href={source === "codex" ? "/?source=codex" : "/"}
            className="text-slate-400 hover:text-slate-200 mb-8 inline-block"
          >
            ← トップに戻る
          </Link>
          <h1 className="text-2xl font-bold mb-4">リリースが見つかりません</h1>
          <p className="text-slate-400">
            バージョン {version} の情報は見つかりませんでした。
          </p>
        </div>
      </main>
    );
  }

  // Codex リリース表示
  if (source === "codex" && codexRelease) {
    const relevance = codexRelease.relevance;
    const explanations = codexRelease.explanations;
    const highlights = codexRelease.highlights_ja?.length ? codexRelease.highlights_ja : codexRelease.highlights_en;

    // 影響あり項目を構築
    const affectedItems = (relevance?.affected_indices ?? []).map(idx => ({
      text: highlights[idx],
      explanation: explanations?.[String(idx)],
    })).filter(item => item.text);

    // 機能提案項目を構築
    const opportunityItems = relevance?.opportunities ?? [];

    const hasActionItems = codexRelease.action_items && codexRelease.action_items.length > 0;

    return (
      <main className="min-h-screen bg-slate-950 text-slate-100">
        <div className="max-w-4xl mx-auto px-4 py-12">
          {/* Back Link */}
          <Link
            href="/?source=codex"
            className="text-slate-400 hover:text-slate-200 mb-8 inline-block"
          >
            ← トップに戻る
          </Link>

          {/* Header */}
          <header className="mb-8">
            <h1 className="text-3xl font-bold mb-2">
              {codexRelease.version} の分析結果から生成されたアクションアイテム
            </h1>
            <p className="text-slate-400 mb-2">リリース日: {codexRelease.date}</p>
            <a
              href={codexRelease.link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-emerald-400 hover:text-emerald-300 text-sm mt-3 inline-block"
            >
              GitHub で原文を見る →
            </a>
          </header>

          {/* 🎯 あなたに影響 */}
          {affectedItems.length > 0 && (
            <section className="mb-8">
              <h2 className="text-lg font-semibold mb-3 text-emerald-400">🎯 あなたに影響</h2>
              <p className="text-slate-500 text-sm mb-3">この更新であなたの環境に影響がある変更です</p>
              <div className="space-y-3">
                {affectedItems.map((item, i) => (
                  <div
                    key={i}
                    className="p-4 rounded-lg border bg-emerald-500/10 border-emerald-500/30"
                  >
                    <p className="text-slate-200">{item.text}</p>
                    {item.explanation && (
                      <div className="mt-2 p-2 bg-emerald-500/5 rounded text-sm text-emerald-300/80">
                        💬 {item.explanation}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* 💡 有効にすると使える */}
          {opportunityItems.length > 0 && (
            <section className="mb-8">
              <h2 className="text-lg font-semibold mb-3 text-amber-400">💡 有効にすると使える</h2>
              <p className="text-slate-500 text-sm mb-3">設定を有効化すると使える新機能です</p>
              <div className="space-y-3">
                {opportunityItems.map((item, i) => {
                  const itemKey = `opportunity-${i}`;
                  return (
                    <div
                      key={i}
                      className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                        selected.has(itemKey)
                          ? "bg-amber-500/20 border-amber-400"
                          : "bg-amber-500/10 border-amber-500/30 hover:bg-amber-500/15"
                      }`}
                      onClick={() => toggleItem(itemKey)}
                    >
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={selected.has(itemKey)}
                          onChange={() => toggleItem(itemKey)}
                          onClick={(e) => e.stopPropagation()}
                          className="mt-1 w-4 h-4 rounded border-amber-500 text-amber-500 focus:ring-amber-500 bg-slate-800"
                        />
                        <div className="flex-1">
                          <p className="text-slate-200">{item.feature} を有効化: {item.benefit}</p>
                          {item.projects && item.projects.length > 0 && (
                            <div className="mt-2 text-sm text-amber-300/80">
                              対象: {item.projects.join(", ")}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* 📋 アクションアイテム */}
          {hasActionItems && (
            <section className="mb-8">
              <h2 className="text-lg font-semibold mb-3 text-violet-400">📋 アクションアイテム</h2>
              <p className="text-slate-500 text-sm mb-3">この更新から生成されたタスク</p>
              <div className="space-y-3">
                {codexRelease.action_items!.map((item, i) => {
                  const itemKey = `action-${i}`;
                  return (
                    <div
                      key={i}
                      className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                        selected.has(itemKey)
                          ? "bg-violet-500/20 border-violet-400"
                          : "bg-slate-900 border-slate-800 hover:bg-slate-800"
                      }`}
                      onClick={() => toggleItem(itemKey)}
                    >
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={selected.has(itemKey)}
                          onChange={() => toggleItem(itemKey)}
                          onClick={(e) => e.stopPropagation()}
                          className="mt-1 w-4 h-4 rounded border-violet-500 text-violet-500 focus:ring-violet-500 bg-slate-800"
                        />
                        <span className={`px-2 py-0.5 rounded text-xs shrink-0 ${
                          item.category === "security" ? "bg-red-900/50 text-red-300" :
                          item.category === "breaking" ? "bg-rose-900/50 text-rose-300" :
                          item.category === "model" ? "bg-purple-900/50 text-purple-300" :
                          item.category === "opportunity" ? "bg-amber-900/50 text-amber-300" :
                          item.category === "affected" ? "bg-emerald-900/50 text-emerald-300" :
                          "bg-slate-700 text-slate-300"
                        }`}>
                          {item.category}
                        </span>
                        <div className="flex-1">
                          <p className="text-slate-200">{item.task}</p>
                          <p className="text-slate-500 text-sm mt-1">根拠: {item.source_feature}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* 原文 (English) - 折りたたみ */}
          <section className="mb-8">
            <details className="group">
              <summary className="text-lg font-semibold mb-3 text-slate-400 cursor-pointer list-none flex items-center gap-2">
                <span className="text-sm">▶</span>
                <span className="group-open:hidden">原文 (English) を表示</span>
                <span className="hidden group-open:inline">原文 (English)</span>
              </summary>
              <div className="mt-3 p-4 bg-slate-900/50 border border-slate-800 rounded-lg">
                <ul className="text-slate-500 text-sm space-y-1">
                  {codexRelease.highlights_en.map((h, i) => (
                    <li key={i}>・{h}</li>
                  ))}
                </ul>
              </div>
            </details>
          </section>

          {/* Footer */}
          <footer className="mt-12 pt-8 border-t border-slate-800 text-center text-slate-500 text-sm">
            <p>AI Update Radar - 自分用ダッシュボード</p>
          </footer>
        </div>

        {/* 送信フローティングバー */}
        {(selected.size > 0 || submitResult) && (
          <div className="fixed bottom-0 left-0 right-0 bg-slate-900/95 backdrop-blur border-t border-slate-700 p-4">
            <div className="max-w-4xl mx-auto flex items-center justify-between">
              <div className="flex items-center gap-4">
                <span className="text-slate-300">
                  <span className="text-violet-400 font-bold">{selected.size}</span> 件選択中
                </span>
                {relayStatus === "connected" && (
                  <span className="text-emerald-400 text-sm">● Relay 接続中</span>
                )}
                {relayStatus === "disconnected" && (
                  <span className="text-red-400 text-sm">● Relay 未接続</span>
                )}
                {relayStatus === "checking" && (
                  <span className="text-slate-400 text-sm">● 確認中...</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setSelected(new Set())}
                  className="px-4 py-2 text-slate-400 hover:text-slate-200 transition-colors"
                >
                  クリア
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={selected.size === 0 || submitting || relayStatus !== "connected"}
                  className={`px-6 py-2 rounded-lg font-semibold transition-colors ${
                    submitting
                      ? "bg-slate-700 text-slate-400 cursor-wait"
                      : selected.size === 0 || relayStatus !== "connected"
                      ? "bg-slate-700 text-slate-500 cursor-not-allowed"
                      : "bg-violet-600 hover:bg-violet-500 text-white"
                  }`}
                >
                  {submitting ? "送信中..." : "タスクとして送信"}
                </button>
              </div>
            </div>
            {submitResult && (
              <div className={`max-w-4xl mx-auto mt-2 flex items-center justify-between ${submitResult.success ? "text-emerald-400" : "text-red-400"}`}>
                <span className="text-sm font-medium">
                  {submitResult.success ? "✓ " : "✗ "}{submitResult.message}
                </span>
                <button
                  onClick={() => setSubmitResult(null)}
                  className="text-slate-400 hover:text-slate-200 text-sm"
                >
                  閉じる
                </button>
              </div>
            )}
          </div>
        )}
      </main>
    );
  }

  // Claude Code リリース表示（既存コード）
  if (!release) return null;
  const hasMeanings = release.meanings && release.meanings.length > 0;

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-4xl mx-auto px-4 py-12">
        {/* Back Link */}
        <Link
          href="/"
          className="text-slate-400 hover:text-slate-200 mb-8 inline-block"
        >
          ← トップに戻る
        </Link>

        {/* Header */}
        <header className="mb-8">
          <h1 className="text-3xl font-bold mb-2">
            Claude Code {release.version}
          </h1>
          <p className="text-slate-400 mb-2">リリース日: {release.date}</p>
          <a
            href={release.link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-violet-400 hover:text-violet-300 text-sm mt-3 inline-block"
          >
            GitHub で原文を見る →
          </a>
        </header>

        {/* Meanings (詳細解説) - カテゴリ別表示 */}
        {hasMeanings ? (
          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-violet-400">
              変更点の解説
            </h2>
            <div className="space-y-6">
              {/* カテゴリごとにグループ化 */}
              {Object.entries(CATEGORY_CONFIG)
                .sort(([, a], [, b]) => a.order - b.order)
                .map(([categoryKey, config]) => {
                  const items = release.meanings!.filter(
                    (m) => (m.category || "improvement") === categoryKey
                  );
                  if (items.length === 0) return null;

                  return (
                    <div key={categoryKey}>
                      <h3 className={`text-lg font-semibold mb-3 ${config.color}`}>
                        {config.label}
                      </h3>
                      <div className="space-y-3">
                        {items.map((item, i) => (
                          <div
                            key={i}
                            className={`p-4 bg-slate-900 border-l-4 ${config.border} rounded-r-lg`}
                          >
                            <h4 className="font-semibold text-slate-100 mb-1">
                              {item.title}
                            </h4>
                            <p className="text-slate-400 text-sm leading-relaxed">
                              {item.meaning}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
            </div>
          </section>
        ) : (
          /* Fallback: highlights_ja */
          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-violet-400">
              主な変更点
            </h2>
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg">
              <ul className="text-slate-300 text-sm space-y-2">
                {(release.highlights_ja.length > 0
                  ? release.highlights_ja
                  : release.highlights_en
                ).map((h, i) => (
                  <li key={i}>・{h}</li>
                ))}
              </ul>
            </div>
          </section>
        )}

        {/* Original highlights (English) */}
        <section className="mb-8 mt-8">
          <h2 className="text-lg font-semibold mb-3 text-slate-400">
            原文 (English)
          </h2>
          <div className="p-4 bg-slate-900/50 border border-slate-800 rounded-lg">
            <ul className="text-slate-500 text-sm space-y-1">
              {release.highlights_en.map((h, i) => (
                <li key={i}>・{h}</li>
              ))}
            </ul>
          </div>
        </section>

        {/* Footer */}
        <footer className="mt-12 pt-8 border-t border-slate-800 text-center text-slate-500 text-sm">
          <p>AI Update Radar - 自分用ダッシュボード</p>
        </footer>
      </div>
    </main>
  );
}
