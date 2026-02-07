"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

type SourceTab = "claude" | "codex";

interface ActionItem {
  task: string;
  source_feature: string;
  priority: number;
  project: string;
  category: "dev" | "business" | "tooling";
  source?: string;
}

interface DevImprovement {
  project: string;
  suggestion: string;
  source_feature: string;
  what_it_is?: string;
  merit?: string;
  demerit?: string;
  priority: string;
  target_area?: string;
  expected_impact?: string;
  effort?: string;
}

interface BusinessOpportunity {
  title: string;
  source_feature: string;
  what_it_is?: string;
  merit?: string;
  demerit?: string;
  description: string;
  affected_projects?: string[];
  potential_value?: string;
  action_required?: string;
}

interface Attribution {
  affected_component: string;
  issue_type: string;
  patch_location: string;
  classification: "Upstream" | "Downstream" | "Mixed" | "Unknown";
  scope_target: string;
  risk_level: "Low" | "Med" | "High";
}

interface AnalysisData {
  version: string;
  analyzed_at: string;
  action_items: ActionItem[];
  dev_improvements: DevImprovement[];
  business_opportunities: BusinessOpportunity[];
  attribution?: Attribution;
  anti_patterns?: string[];
}

interface CodexReleaseActionItem {
  task: string;
  source_feature: string;
  category: string;
}

interface CodexRelease {
  version: string;
  date: string;
  action_items?: CodexReleaseActionItem[];
  prerelease: boolean;
}

interface CodexReleasesData {
  releases: CodexRelease[];
}

interface SubmitResult {
  success: boolean;
  message: string;
  results?: Array<{
    task_id?: string;
    success: boolean;
    error?: string;
    item: ActionItem;
  }>;
}

type RelayStatus = "checking" | "connected" | "disconnected";

function ActionsContent() {
  const searchParams = useSearchParams();
  const initialSource = searchParams.get("source") === "codex" ? "codex" : "claude";
  const [sourceTab, setSourceTab] = useState<SourceTab>(initialSource);
  const [claudeData, setClaudeData] = useState<AnalysisData | null>(null);
  const [codexData, setCodexData] = useState<AnalysisData | null>(null);
  const [codexReleasesData, setCodexReleasesData] = useState<CodexReleasesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [filter, setFilter] = useState<"all" | "dev" | "business">("all");
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<SubmitResult | null>(null);
  const [relayStatus, setRelayStatus] = useState<RelayStatus>("checking");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  // 現在のタブのデータ
  const data = sourceTab === "claude" ? claudeData : codexData;

  // 分析データの読み込み（キャッシュバスト付き）
  useEffect(() => {
    const cacheBust = `?t=${Date.now()}`;
    Promise.all([
      fetch(`/data/analysis.json${cacheBust}`).then((res) => res.json()).catch(() => null),
      fetch(`/data/codex_analysis.json${cacheBust}`).then((res) => res.json()).catch(() => null),
      fetch(`/data/codex_releases.json${cacheBust}`).then((res) => res.json()).catch(() => null),
    ]).then(([claude, codex, codexReleases]) => {
      setClaudeData(claude);
      setCodexData(codex);
      setCodexReleasesData(codexReleases);
      setLoading(false);
    });
  }, []);

  // タブ切り替え時に選択をリセット
  useEffect(() => {
    setSelected(new Set());
    setExpanded(new Set());
  }, [sourceTab]);

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
    // 30秒ごとに再チェック
    const interval = setInterval(checkRelay, 30000);
    return () => clearInterval(interval);
  }, []);

  const toggleItem = (priority: number) => {
    const newSelected = new Set(selected);
    if (newSelected.has(priority)) {
      newSelected.delete(priority);
    } else {
      newSelected.add(priority);
    }
    setSelected(newSelected);
  };

  const selectAll = () => {
    if (!data) return;
    const filtered = filteredItems();
    const allPriorities = new Set(filtered.map((item) => item.priority));
    setSelected(allPriorities);
  };

  const clearAll = () => {
    setSelected(new Set());
  };

  const filteredItems = () => {
    if (!data) return [];
    if (filter === "all") return data.action_items;
    return data.action_items.filter((item) => item.category === filter);
  };

  const handleSubmit = async () => {
    if (selected.size === 0 || !data) return;

    setSubmitting(true);
    setSubmitResult(null);

    let selectedItems: ActionItem[];

    if (sourceTab === "codex") {
      // Codex タブ: dev_improvements の「機能提案」から選択されたものを ActionItem 形式に変換
      const featureProposals = data.dev_improvements?.filter(d => d.source_feature.startsWith("機能提案")) ?? [];
      selectedItems = featureProposals
        .map((item, i) => ({ item, itemKey: 1000 + i }))
        .filter(({ itemKey }) => selected.has(itemKey))
        .map(({ item, itemKey }): ActionItem => ({
          task: item.suggestion,
          source_feature: item.source_feature,
          priority: itemKey,
          project: item.project,
          category: "tooling",
          source: "codex",
        }));
    } else {
      // Claude タブ: action_items から直接選択
      selectedItems = data.action_items.filter((item) =>
        selected.has(item.priority)
      );
    }

    // 選択アイテムが空の場合はエラー
    if (selectedItems.length === 0) {
      setSubmitResult({
        success: false,
        message: "送信するアイテムがありません",
      });
      setSubmitting(false);
      return;
    }

    try {
      const response = await fetch("/api/submit-tasks", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          version: data.version,
          items: selectedItems,
        }),
      });

      const result: SubmitResult = await response.json();
      setSubmitResult(result);

      // 成功した場合、選択をクリア
      if (result.success) {
        setSelected(new Set());
      }

      // ローカルストレージにも記録（履歴用）
      const rejected = sourceTab === "codex"
        ? [] // Codex では rejected を追跡しない
        : data.action_items.filter((item) => !selected.has(item.priority));
      const decisions = {
        version: data.version,
        decided_at: new Date().toISOString(),
        source: sourceTab,
        adopted: selectedItems,
        rejected,
        submit_result: result,
      };
      localStorage.setItem("action_decisions", JSON.stringify(decisions));

    } catch (error) {
      setSubmitResult({
        success: false,
        message: error instanceof Error ? error.message : "送信に失敗しました",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const getPriorityColor = (priority: string | number) => {
    const p = typeof priority === "string" ? priority : "";
    if (p === "HIGH" || (typeof priority === "number" && priority <= 2))
      return "text-red-400";
    if (p === "MEDIUM" || (typeof priority === "number" && priority <= 4))
      return "text-yellow-400";
    return "text-green-400";
  };

  const getCategoryIcon = (category: string) => {
    if (category === "dev") return "🔧";
    if (category === "tooling") return "⚙️";
    return "💼";
  };

  const toggleExpand = (priority: number) => {
    const newExpanded = new Set(expanded);
    if (newExpanded.has(priority)) {
      newExpanded.delete(priority);
    } else {
      newExpanded.add(priority);
    }
    setExpanded(newExpanded);
  };

  // アクションアイテムに対応する詳細情報を取得
  const getItemDetail = (item: ActionItem) => {
    if (!data) return null;

    if (item.category === "dev") {
      return data.dev_improvements.find(
        (d) => d.source_feature === item.source_feature && d.project === item.project
      );
    } else {
      return data.business_opportunities.find(
        (b) => b.source_feature === item.source_feature
      );
    }
  };

  const getRelayStatusDisplay = () => {
    switch (relayStatus) {
      case "checking":
        return { icon: "⏳", text: "確認中", color: "text-slate-400" };
      case "connected":
        return { icon: "🟢", text: "接続済", color: "text-green-400" };
      case "disconnected":
        return { icon: "🔴", text: "未接続", color: "text-red-400" };
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

  if (!data) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100">
        <div className="max-w-5xl mx-auto px-4 py-12">
          <p className="text-slate-400">分析データがありません</p>
          <Link href="/" className="text-violet-400 hover:text-violet-300 mt-4 inline-block">
            ← トップに戻る
          </Link>
        </div>
      </main>
    );
  }

  const items = filteredItems();
  const relayStatusDisplay = getRelayStatusDisplay();

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-5xl mx-auto px-4 py-12">
        {/* Header */}
        <header className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-3xl font-bold">アクションアイテム レビュー</h1>
            <Link
              href="/"
              className="text-slate-400 hover:text-slate-200 text-sm"
            >
              ← トップに戻る
            </Link>
          </div>

          {/* Source Tabs */}
          <div className="flex items-center gap-2 mb-4">
            <button
              onClick={() => setSourceTab("claude")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                sourceTab === "claude"
                  ? "bg-violet-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:text-white"
              }`}
            >
              Claude Code {claudeData && `(${claudeData.action_items.length})`}
            </button>
            <button
              onClick={() => setSourceTab("codex")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                sourceTab === "codex"
                  ? "bg-emerald-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:text-white"
              }`}
            >
              Codex {codexData && `(${codexData.action_items.length})`}
            </button>
          </div>

          <p className="text-slate-400">
            {data.version} の分析結果から生成されたアクションアイテム
          </p>
          <div className="flex items-center gap-4 mt-2">
            <p className="text-slate-500 text-sm">
              分析日時: {new Date(data.analyzed_at).toLocaleString("ja-JP")}
            </p>
            <div className={`text-sm flex items-center gap-1 ${relayStatusDisplay.color}`}>
              <span>{relayStatusDisplay.icon}</span>
              <span>Relay API: {relayStatusDisplay.text}</span>
            </div>
          </div>
        </header>

        {/* Attribution（帰属判定） */}
        {data.attribution && (
          <section className="mb-6 p-4 bg-slate-900 border border-slate-800 rounded-lg">
            <div className="flex items-center gap-3 mb-3">
              <span className={`px-2 py-1 rounded text-sm font-medium ${
                data.attribution.classification === "Upstream"
                  ? "bg-blue-900/50 text-blue-300"
                  : data.attribution.classification === "Downstream"
                  ? "bg-amber-900/50 text-amber-300"
                  : data.attribution.classification === "Mixed"
                  ? "bg-purple-900/50 text-purple-300"
                  : "bg-slate-700 text-slate-300"
              }`}>
                {data.attribution.classification}
              </span>
              <span className={`text-sm ${
                data.attribution.risk_level === "High" ? "text-red-400" :
                data.attribution.risk_level === "Med" ? "text-yellow-400" : "text-green-400"
              }`}>
                Risk: {data.attribution.risk_level}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-slate-500">影響対象:</span>
                <span className="text-slate-300 ml-2">{data.attribution.affected_component}</span>
              </div>
              <div>
                <span className="text-slate-500">パッチ場所:</span>
                <span className="text-slate-300 ml-2">{data.attribution.patch_location}</span>
              </div>
              <div>
                <span className="text-slate-500">適用範囲:</span>
                <span className="text-slate-300 ml-2">{data.attribution.scope_target}</span>
              </div>
              <div>
                <span className="text-slate-500">種別:</span>
                <span className="text-slate-300 ml-2">{data.attribution.issue_type}</span>
              </div>
            </div>
          </section>
        )}

        {/* Anti-Patterns（やってはいけない誤解） */}
        {data.anti_patterns && data.anti_patterns.length > 0 && (
          <section className="mb-6 p-4 bg-red-950/30 border border-red-900/50 rounded-lg">
            <h3 className="text-sm font-medium text-red-400 mb-2">⚠️ やってはいけない誤解</h3>
            <ul className="text-sm text-red-300/80 space-y-1">
              {data.anti_patterns.map((pattern, i) => (
                <li key={i}>・{pattern}</li>
              ))}
            </ul>
          </section>
        )}

        {/* Submit Result */}
        {submitResult && (
          <div
            className={`mb-6 p-4 rounded-lg border ${
              submitResult.success
                ? "bg-green-900/30 border-green-700"
                : "bg-red-900/30 border-red-700"
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              <span>{submitResult.success ? "✅" : "❌"}</span>
              <span className="font-medium">{submitResult.message}</span>
            </div>
            {submitResult.results && (
              <div className="text-sm space-y-1 mt-2">
                {submitResult.results.map((r, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span>{r.success ? "✓" : "✗"}</span>
                    <span className="text-slate-300">{r.item.task.slice(0, 50)}...</span>
                    {r.task_id && (
                      <span className="text-slate-500 text-xs">({r.task_id})</span>
                    )}
                    {r.error && (
                      <span className="text-red-400 text-xs">{r.error}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
            <button
              onClick={() => setSubmitResult(null)}
              className="mt-3 text-sm text-slate-400 hover:text-white"
            >
              閉じる
            </button>
          </div>
        )}

        {/* Filter & Actions */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <span className="text-slate-400 text-sm">フィルター:</span>
            <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
              {(["all", "dev", "business"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-3 py-1 rounded text-sm transition-colors ${
                    filter === f
                      ? "bg-violet-600 text-white"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {f === "all" ? "すべて" : f === "dev" ? "🔧 開発" : "💼 経営"}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={selectAll}
              className="px-3 py-1 text-sm text-slate-400 hover:text-white"
            >
              全選択
            </button>
            <button
              onClick={clearAll}
              className="px-3 py-1 text-sm text-slate-400 hover:text-white"
            >
              全解除
            </button>
          </div>
        </div>

        {/* Action Items - Claude Code のみ表示 */}
        {sourceTab === "claude" && (
        <section className="mb-8">
          <div className="space-y-3">
            {items.map((item) => {
              const detail = getItemDetail(item);
              const isExpanded = expanded.has(item.priority);
              const isDevItem = item.category === "dev";
              const devDetail = isDevItem ? (detail as DevImprovement | undefined) : undefined;
              const bizDetail = !isDevItem ? (detail as BusinessOpportunity | undefined) : undefined;

              return (
                <div
                  key={item.priority}
                  className={`rounded-lg border transition-all ${
                    selected.has(item.priority)
                      ? "bg-violet-900/30 border-violet-500"
                      : "bg-slate-900 border-slate-800"
                  }`}
                >
                  {/* ヘッダー部分 */}
                  <div
                    onClick={() => toggleExpand(item.priority)}
                    className="p-4 cursor-pointer hover:bg-slate-800/50 transition-colors"
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-1">
                        <input
                          type="checkbox"
                          checked={selected.has(item.priority)}
                          onClick={(e) => e.stopPropagation()}
                          onChange={() => toggleItem(item.priority)}
                          className="w-5 h-5 rounded border-slate-600 bg-slate-800 text-violet-500 focus:ring-violet-500"
                        />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-lg">{getCategoryIcon(item.category)}</span>
                          <span className={`text-sm font-medium ${getPriorityColor(item.priority)}`}>
                            #{item.priority}
                          </span>
                          <span className="text-xs px-2 py-0.5 bg-slate-700 text-slate-300 rounded">
                            {item.project}
                          </span>
                          <span className="text-slate-500 text-sm ml-auto">
                            {isExpanded ? "▼" : "▶"}
                          </span>
                        </div>
                        <p className="text-slate-200">{item.task}</p>
                      </div>
                    </div>
                  </div>

                  {/* 展開時の詳細 */}
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-0 ml-12 border-t border-slate-800">
                      <div className="pt-4 space-y-2 text-sm">
                        {/* 根拠（共通） */}
                        <div className="flex">
                          <span className="text-slate-500 w-28 shrink-0">根拠:</span>
                          <span className="text-slate-300">{item.source_feature}</span>
                        </div>

                        {/* 開発アイテムの詳細 */}
                        {isDevItem && devDetail && (
                          <>
                            {devDetail.target_area && (
                              <div className="flex">
                                <span className="text-slate-500 w-28 shrink-0">対象領域:</span>
                                <span className="text-slate-300">{devDetail.target_area}</span>
                              </div>
                            )}
                            {devDetail.expected_impact && (
                              <div className="flex">
                                <span className="text-slate-500 w-28 shrink-0">期待効果:</span>
                                <span className="text-emerald-400">{devDetail.expected_impact}</span>
                              </div>
                            )}
                            {devDetail.effort && (
                              <div className="flex">
                                <span className="text-slate-500 w-28 shrink-0">工数:</span>
                                <span className="text-slate-300">{devDetail.effort}</span>
                              </div>
                            )}
                            {devDetail.suggestion && (
                              <div className="mt-3 p-3 bg-slate-800/50 rounded text-slate-400 text-xs">
                                {devDetail.suggestion}
                              </div>
                            )}
                          </>
                        )}

                        {/* ビジネスアイテムの詳細 */}
                        {!isDevItem && bizDetail && (
                          <>
                            {bizDetail.potential_value && (
                              <div className="flex">
                                <span className="text-slate-500 w-28 shrink-0">期待価値:</span>
                                <span className="text-amber-400">{bizDetail.potential_value}</span>
                              </div>
                            )}
                            {bizDetail.action_required && (
                              <div className="flex">
                                <span className="text-slate-500 w-28 shrink-0">必要な行動:</span>
                                <span className="text-slate-300">{bizDetail.action_required}</span>
                              </div>
                            )}
                            {bizDetail.affected_projects && bizDetail.affected_projects.length > 0 && (
                              <div className="flex">
                                <span className="text-slate-500 w-28 shrink-0">関連PJ:</span>
                                <span className="text-slate-300">{bizDetail.affected_projects.join(", ")}</span>
                              </div>
                            )}
                            {bizDetail.description && (
                              <div className="mt-3 p-3 bg-slate-800/50 rounded text-slate-400 text-xs">
                                {bizDetail.description}
                              </div>
                            )}
                          </>
                        )}

                        {/* 詳細情報がない場合 */}
                        {!detail && (
                          <p className="text-slate-500 text-xs">詳細情報がありません</p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
        )}

        {/* Codex: カテゴリ別表示 */}
        {sourceTab === "codex" && (
          <>
            {/* 🎯 あなたに影響（情報表示） */}
            {data.dev_improvements?.filter(d => d.source_feature.startsWith("影響あり")).length > 0 && (
              <section className="mb-8">
                <h2 className="text-lg font-semibold mb-3 text-emerald-400">🎯 あなたに影響</h2>
                <p className="text-slate-500 text-sm mb-3">この更新であなたの環境に影響がある変更です</p>
                <div className="space-y-3">
                  {data.dev_improvements
                    ?.filter(d => d.source_feature.startsWith("影響あり"))
                    .map((item, i) => (
                      <div
                        key={i}
                        className="p-4 rounded-lg border bg-emerald-500/10 border-emerald-500/30"
                      >
                        <p className="text-slate-200">{item.suggestion}</p>
                        {item.what_it_is && (
                          <div className="mt-2 p-2 bg-emerald-500/5 rounded text-sm text-emerald-300/80">
                            💬 {item.what_it_is}
                          </div>
                        )}
                      </div>
                    ))}
                </div>
              </section>
            )}

            {/* 💡 有効にすると使える（機能提案） */}
            {data.dev_improvements?.filter(d => d.source_feature.startsWith("機能提案")).length > 0 && (
              <section className="mb-8">
                <h2 className="text-lg font-semibold mb-3 text-amber-400">💡 有効にすると使える</h2>
                <p className="text-slate-500 text-sm mb-3">設定を有効化すると使える新機能です</p>
                <div className="space-y-3">
                  {data.dev_improvements
                    ?.filter(d => d.source_feature.startsWith("機能提案"))
                    .map((item, i) => {
                      // 対応する action_item を探す（タスク用）
                      const actionItem = data.action_items?.find(a =>
                        a.source_feature.startsWith("機能提案") &&
                        (item.suggestion.toLowerCase().includes(a.source_feature.replace("機能提案: ", "").toLowerCase()) ||
                         a.task.toLowerCase().includes(item.suggestion.substring(0, 20).toLowerCase()))
                      );
                      const itemKey = actionItem?.priority ?? 1000 + i;
                      return (
                        <div
                          key={itemKey}
                          className={`p-4 rounded-lg border transition-all ${
                            selected.has(itemKey)
                              ? "bg-amber-900/30 border-amber-500"
                              : "bg-amber-500/10 border-amber-500/30"
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            <input
                              type="checkbox"
                              checked={selected.has(itemKey)}
                              onChange={() => toggleItem(itemKey)}
                              className="mt-1 w-5 h-5 rounded border-amber-600 bg-slate-800 text-amber-500 focus:ring-amber-500"
                            />
                            <div className="flex-1">
                              <p className="text-slate-200">{item.suggestion}</p>
                              {item.what_it_is && (
                                <div className="mt-2 p-2 bg-amber-500/5 rounded text-sm text-amber-300/80">
                                  💬 {item.what_it_is}
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

            {/* 📋 リリース別アクションアイテム履歴 */}
            {codexReleasesData && (
              <section className="mb-8">
                <h2 className="text-lg font-semibold mb-3 text-slate-300">📋 リリース別アクションアイテム</h2>
                <p className="text-slate-500 text-sm mb-3">過去のリリースから生成されたアクションアイテム（クリックで詳細）</p>
                <div className="space-y-4">
                  {codexReleasesData.releases
                    .filter(r => !r.prerelease && r.action_items && r.action_items.length > 0)
                    .map((release) => (
                      <Link
                        key={release.version}
                        href={`/releases/${release.version}`}
                        className="block p-4 rounded-lg border bg-slate-800/50 border-slate-700 hover:bg-slate-800 hover:border-slate-600 transition-colors"
                      >
                        <div className="flex items-center gap-2 mb-3">
                          <span className="text-emerald-400 font-semibold">{release.version}</span>
                          <span className="text-slate-500 text-sm">{release.date}</span>
                          <span className="text-xs px-2 py-0.5 bg-slate-700 text-slate-300 rounded">
                            {release.action_items?.length ?? 0} 件
                          </span>
                          <span className="text-slate-500 text-sm ml-auto">詳細 →</span>
                        </div>
                        <ul className="space-y-2">
                          {release.action_items?.map((item, idx) => (
                            <li key={idx} className="flex items-start gap-2 text-sm">
                              <span className={`px-2 py-0.5 rounded text-xs ${
                                item.category === "security" ? "bg-red-900/50 text-red-300" :
                                item.category === "breaking" ? "bg-rose-900/50 text-rose-300" :
                                item.category === "model" ? "bg-purple-900/50 text-purple-300" :
                                item.category === "opportunity" ? "bg-amber-900/50 text-amber-300" :
                                item.category === "affected" ? "bg-emerald-900/50 text-emerald-300" :
                                "bg-slate-700 text-slate-300"
                              }`}>
                                {item.category}
                              </span>
                              <span className="text-slate-300">{item.task}</span>
                            </li>
                          ))}
                        </ul>
                      </Link>
                    ))}
                  {codexReleasesData.releases.filter(r => !r.prerelease && r.action_items && r.action_items.length > 0).length === 0 && (
                    <p className="text-slate-500 text-sm">アクションアイテムのあるリリースはありません</p>
                  )}
                </div>
              </section>
            )}
          </>
        )}

        {/* Summary & Submit */}
        <section className="sticky bottom-4">
          <div className="p-4 bg-slate-900 border border-slate-700 rounded-lg shadow-lg">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-slate-400">選択中: </span>
                <span className="text-violet-400 font-bold">{selected.size}</span>
                <span className="text-slate-400"> / {items.length} 件</span>
              </div>
              <div className="flex items-center gap-3">
                {relayStatus === "disconnected" && (
                  <span className="text-xs text-red-400">
                    Relay API が未接続です
                  </span>
                )}
                <button
                  onClick={handleSubmit}
                  disabled={selected.size === 0 || submitting || relayStatus !== "connected"}
                  className={`px-6 py-2 rounded-lg font-medium transition-colors ${
                    submitting
                      ? "bg-violet-700 text-white cursor-wait"
                      : selected.size === 0 || relayStatus !== "connected"
                      ? "bg-slate-700 text-slate-500 cursor-not-allowed"
                      : "bg-violet-600 text-white hover:bg-violet-500"
                  }`}
                >
                  {submitting ? "送信中..." : "task-receiver に送信"}
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* Claude Code: Dev Improvements Preview */}
        {sourceTab === "claude" && data.dev_improvements && data.dev_improvements.length > 0 && (
          <section className="mt-12">
            <h2 className="text-xl font-semibold mb-4">開発改善提案（詳細）</h2>
            <div className="space-y-4">
              {data.dev_improvements.map((imp, i) => (
                <div
                  key={i}
                  className="p-4 bg-slate-900 border border-slate-800 rounded-lg"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className={`text-sm font-medium ${getPriorityColor(
                        imp.priority
                      )}`}
                    >
                      {imp.priority}
                    </span>
                    <span className="text-slate-300 font-medium">
                      {imp.project}
                    </span>
                  </div>
                  <p className="text-slate-200 mb-3">{imp.suggestion}</p>

                  {/* What it is / Merit / Demerit */}
                  {imp.what_it_is && (
                    <div className="mb-3 p-3 bg-slate-800/50 rounded text-sm">
                      <p className="text-slate-300 mb-2">
                        <span className="text-slate-500">何ができる: </span>
                        {imp.what_it_is}
                      </p>
                      {(imp.merit || imp.demerit) && (
                        <div className="grid grid-cols-2 gap-3 mt-2">
                          {imp.merit && (
                            <div className="flex items-start gap-2">
                              <span className="text-green-400">✓</span>
                              <span className="text-green-300/80">{imp.merit}</span>
                            </div>
                          )}
                          {imp.demerit && (
                            <div className="flex items-start gap-2">
                              <span className="text-red-400">✗</span>
                              <span className="text-red-300/80">{imp.demerit}</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {imp.source_feature && (
                    <p className="text-slate-500 text-sm">
                      根拠: {imp.source_feature}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Business Opportunities Preview */}
        {data.business_opportunities && data.business_opportunities.length > 0 && (
          <section className="mt-12">
            <h2 className="text-xl font-semibold mb-4">経営機会（詳細）</h2>
            <div className="space-y-4">
              {data.business_opportunities.map((opp, i) => (
                <div
                  key={i}
                  className="p-4 bg-slate-900 border border-slate-800 rounded-lg"
                >
                  <h3 className="text-slate-200 font-medium mb-2">
                    💡 {opp.title}
                  </h3>
                  <p className="text-slate-400 text-sm mb-3">{opp.description}</p>

                  {/* What it is / Merit / Demerit */}
                  {opp.what_it_is && (
                    <div className="mb-3 p-3 bg-slate-800/50 rounded text-sm">
                      <p className="text-slate-300 mb-2">
                        <span className="text-slate-500">何ができる: </span>
                        {opp.what_it_is}
                      </p>
                      {(opp.merit || opp.demerit) && (
                        <div className="grid grid-cols-2 gap-3 mt-2">
                          {opp.merit && (
                            <div className="flex items-start gap-2">
                              <span className="text-green-400">✓</span>
                              <span className="text-green-300/80">{opp.merit}</span>
                            </div>
                          )}
                          {opp.demerit && (
                            <div className="flex items-start gap-2">
                              <span className="text-red-400">✗</span>
                              <span className="text-red-300/80">{opp.demerit}</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {opp.source_feature && (
                    <p className="text-slate-500 text-sm">
                      根拠: {opp.source_feature}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

export default function ActionsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">Loading...</div>}>
      <ActionsContent />
    </Suspense>
  );
}
