"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

const GITHUB_RELEASES_URL = "https://github.com/anthropics/claude-code/releases";
const CHANGELOG_URL = "https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md";

interface Meaning {
  title: string;
  meaning: string;
}

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

interface Attribution {
  affected_component: string;
  issue_type: string;
  patch_location: string;
  classification: "Upstream" | "Downstream" | "Mixed" | "Unknown";
  scope_target: string;
  risk_level: "Low" | "Med" | "High";
}

interface ActionItem {
  task: string;
  source_feature: string;
  priority: number;
  project: string;
  category: "dev" | "business" | "tooling";
}

interface AnalysisData {
  version: string;
  analyzed_at: string;
  action_items: ActionItem[];
  attribution?: Attribution;
  anti_patterns?: string[];
}

interface CodexImportance {
  level: "normal" | "medium" | "high";
  tags: string[];
}

interface CodexOpportunity {
  feature: string;
  benefit: string;
  projects: string[];
}

interface CodexRelevance {
  applies_to_you: boolean;
  reasons: string[];
  affected_indices: number[];      // 有効な機能に影響
  opportunity_indices: number[];   // 有効にすると使える
  other_indices: number[];         // その他
  opportunities: CodexOpportunity[];
}

interface CategorizedHighlight {
  text: string;
  category: "feature" | "fix" | "improvement" | "security" | "breaking";
}

interface CodexActionItem {
  task: string;
  source_feature: string;
  category: string;
}

interface CodexRelease {
  version: string;
  date: string;
  link: string;
  highlights_en: string[];
  highlights_ja?: string[];
  categorized_highlights?: CategorizedHighlight[];
  explanations?: Record<string, string>;  // インデックス -> 説明
  prerelease: boolean;
  importance: CodexImportance;
  relevance?: CodexRelevance | null;
  action_items?: CodexActionItem[];
}

// Codex カテゴリ設定
const CODEX_CATEGORY_CONFIG = {
  feature: { label: "🚀 新機能", order: 1, color: "text-emerald-400", border: "border-emerald-600" },
  fix: { label: "🐛 修正", order: 2, color: "text-amber-400", border: "border-amber-600" },
  improvement: { label: "🔧 改善", order: 3, color: "text-blue-400", border: "border-blue-600" },
  security: { label: "🔒 セキュリティ", order: 4, color: "text-red-400", border: "border-red-600" },
  breaking: { label: "💥 破壊的変更", order: 5, color: "text-rose-400", border: "border-rose-600" },
} as const;

interface CodexReleasesData {
  updated_at: string;
  releases: CodexRelease[];
}

interface ArticleEvaluation {
  url: string;
  title: string;
  relevance: number; // 1-5
  actionability: number; // 1-5
  summary_ja: string;
  recommended_action: "adopt" | "watch" | "skip";
  prefilter_score: number;
  source_topic: string;
  evaluation_source: "llm" | "fallback";
}

interface ArticleCandidatesData {
  evaluated_at: string;
  total: number;
  llm_evaluated: number;
  fallback_used: number;
  evaluations: ArticleEvaluation[];
}

type ArticleDecision = "approve" | "reject" | "pending";

const features = [
  {
    version: "2.1.x",
    title: "Skills ホットリロード",
    desc: "再起動なしで即反映。スキル開発ループが高速化。",
  },
  {
    version: "2.1.x",
    title: "セッションテレポーテーション（/teleport）",
    desc: "ローカル↔Web移動を前提化。作業の継続性が上がる。",
  },
  {
    version: "2.1.x",
    title: "サブエージェントのフォーク型コンテキスト",
    desc: "分業が現実になる。思考の衝突を減らして並列化。",
  },
  {
    version: "2.1.x",
    title: "リアルタイム思考ブロック表示",
    desc: "何を考えているかが見える。デバッグと運用がしやすい。",
  },
  {
    version: "2.1.x",
    title: "LSP ツール（go-to-definition / references）",
    desc: "エディタ級の体験がCLIへ。探索と修正が速い。",
  },
  {
    version: "2.0.x",
    title: "サンドボックスモード",
    desc: "Linux/Mac でコマンド実行を隔離。安全性向上。",
  },
];

const links = [
  { label: "GitHub Releases", url: GITHUB_RELEASES_URL },
  { label: "CHANGELOG.md", url: CHANGELOG_URL },
  { label: "公式ドキュメント", url: "https://docs.anthropic.com/en/docs/claude-code" },
  { label: "npm パッケージ", url: "https://www.npmjs.com/package/@anthropic-ai/claude-code" },
  { label: "アクションアイテム", url: "/actions", internal: true },
];

type Lang = "en" | "ja";
type Tool = "claude" | "codex" | "articles";

function HomeContent() {
  const [data, setData] = useState<ReleasesData | null>(null);
  const [codexData, setCodexData] = useState<CodexReleasesData | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [codexAnalysis, setCodexAnalysis] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [lang, setLang] = useState<Lang>("ja");
  const [activeTool, setActiveTool] = useState<Tool>("claude");
  const [articleData, setArticleData] = useState<ArticleCandidatesData | null>(null);
  const [articleDecisions, setArticleDecisions] = useState<Record<string, ArticleDecision>>({});
  const searchParams = useSearchParams();

  // URL パラメータから初期タブを設定
  useEffect(() => {
    const source = searchParams.get("source");
    if (source === "codex") {
      setActiveTool("codex");
    } else if (source === "articles") {
      setActiveTool("articles");
    }
  }, [searchParams]);

  // 言語設定を localStorage から復元
  useEffect(() => {
    const saved = localStorage.getItem("lang");
    if (saved === "ja" || saved === "en") {
      setLang(saved);
    }
  }, []);

  // articleDecisions を localStorage から復元
  useEffect(() => {
    const saved = localStorage.getItem("articleDecisions");
    if (saved) {
      try {
        setArticleDecisions(JSON.parse(saved));
      } catch {}
    }
  }, []);

  // 言語変更時に localStorage に保存
  const handleLangChange = (newLang: Lang) => {
    setLang(newLang);
    localStorage.setItem("lang", newLang);
  };

  useEffect(() => {
    const cacheBust = `?t=${Date.now()}`;
    Promise.all([
      fetch(`/data/releases.json${cacheBust}`).then((res) => res.json()),
      fetch(`/data/analysis.json${cacheBust}`).then((res) => res.json()).catch(() => null),
      fetch(`/data/codex_releases.json${cacheBust}`).then((res) => res.json()).catch(() => null),
      fetch(`/data/codex_analysis.json${cacheBust}`).then((res) => res.json()).catch(() => null),
      fetch(`/data/article_candidates.json${cacheBust}`).then((res) => res.json()).catch(() => null),
    ])
      .then(([releasesJson, analysisJson, codexJson, codexAnalysisJson, articleJson]) => {
        setData(releasesJson);
        setAnalysis(analysisJson);
        setCodexData(codexJson);
        setCodexAnalysis(codexAnalysisJson);
        setArticleData(articleJson);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load data:", err);
        setLoading(false);
      });
  }, []);

  const latestReleases = data?.releases.slice(0, 5) ?? [];
  const latestVersion = latestReleases[0]?.version ?? "...";

  // Codex: 最新リリース（prerelease除外）
  const codexImportantReleases = codexData?.releases
    .filter((r) => !r.prerelease)
    .slice(0, 3) ?? [];
  const codexLatestVersion = codexData?.releases.find((r) => !r.prerelease)?.version ?? "...";

  const getImportanceStyle = (level: string) => {
    switch (level) {
      case "high":
        return "bg-red-900/50 text-red-300 border-red-700";
      case "medium":
        return "bg-amber-900/50 text-amber-300 border-amber-700";
      default:
        return "bg-slate-700 text-slate-300 border-slate-600";
    }
  };

  const getClassificationStyle = (classification: string) => {
    switch (classification) {
      case "Upstream":
        return "bg-blue-900/50 text-blue-300 border-blue-700";
      case "Downstream":
        return "bg-amber-900/50 text-amber-300 border-amber-700";
      case "Mixed":
        return "bg-purple-900/50 text-purple-300 border-purple-700";
      default:
        return "bg-slate-700 text-slate-300 border-slate-600";
    }
  };

  const getRiskStyle = (risk: string) => {
    switch (risk) {
      case "High":
        return "text-red-400";
      case "Med":
        return "text-yellow-400";
      default:
        return "text-green-400";
    }
  };

  const getHighlights = (release: Release) => {
    if (lang === "ja" && release.highlights_ja && release.highlights_ja.length > 0) {
      return release.highlights_ja;
    }
    return release.highlights_en || [];
  };

  const handleArticleDecision = (url: string, decision: ArticleDecision) => {
    const updated = { ...articleDecisions, [url]: decision };
    setArticleDecisions(updated);
    localStorage.setItem("articleDecisions", JSON.stringify(updated));
  };

  const handleExportApproved = () => {
    if (!articleData) return;
    const approved = articleData.evaluations.filter(
      (e) => articleDecisions[e.url] === "approve"
    );
    const blob = new Blob(
      [JSON.stringify({ approved, exported_at: new Date().toISOString() }, null, 2)],
      { type: "application/json" }
    );
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = "article_decisions.json";
    a.click();
    URL.revokeObjectURL(blobUrl);
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-5xl mx-auto px-4 py-12">
        {/* Header */}
        <header className="mb-12">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-4xl font-bold">AI Update Radar</h1>
            {/* Language Toggle */}
            <div className="flex items-center gap-2 bg-slate-800 rounded-lg p-1">
              <button
                onClick={() => handleLangChange("en")}
                className={`px-3 py-1 rounded text-sm transition-colors ${
                  lang === "en"
                    ? "bg-violet-600 text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                EN
              </button>
              <button
                onClick={() => handleLangChange("ja")}
                className={`px-3 py-1 rounded text-sm transition-colors ${
                  lang === "ja"
                    ? "bg-violet-600 text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                JA
              </button>
            </div>
          </div>
          <p className="text-slate-400">
            AI ツールの最新アップデートを追跡する自分用ダッシュボード
          </p>
          {data && (
            <p className="text-slate-500 text-sm mt-2">
              最終更新: {new Date(data.updated_at).toLocaleString("ja-JP")}
            </p>
          )}
        </header>

        {/* Quick Links */}
        <section className="mb-12">
          <h2 className="text-xl font-semibold mb-4">クイックリンク</h2>
          <div className="flex flex-wrap gap-3">
            {links.map((link) =>
              (link as { internal?: boolean }).internal ? (
                <a
                  key={link.label}
                  href={link.url}
                  className="px-4 py-2 bg-violet-900/50 hover:bg-violet-800/50 rounded-lg border border-violet-700 transition-colors text-violet-300"
                >
                  {link.label} →
                </a>
              ) : (
                <a
                  key={link.label}
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 transition-colors"
                >
                  {link.label} →
                </a>
              )
            )}
          </div>
        </section>

        {/* Latest Releases - Tabbed */}
        <section className="mb-12">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">最新リリース</h2>
            {/* Tool Tabs */}
            <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
              <button
                onClick={() => setActiveTool("claude")}
                className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
                  activeTool === "claude"
                    ? "bg-violet-600 text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Claude Code
              </button>
              <button
                onClick={() => setActiveTool("codex")}
                className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
                  activeTool === "codex"
                    ? "bg-emerald-600 text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Codex
                {codexImportantReleases.length > 0 && (
                  <span className="ml-1.5 px-1.5 py-0.5 text-xs bg-red-500/80 text-white rounded">
                    {codexImportantReleases.length}
                  </span>
                )}
              </button>
              <button
                onClick={() => setActiveTool("articles")}
                className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
                  activeTool === "articles"
                    ? "bg-sky-600 text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                記事
                {articleData && articleData.evaluations.length > 0 && (
                  <span className="ml-1.5 px-1.5 py-0.5 text-xs bg-sky-500/80 text-white rounded">
                    {articleData.evaluations.length}
                  </span>
                )}
              </button>
            </div>
          </div>
          {loading ? (
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg">
              <p className="text-slate-400">読み込み中...</p>
            </div>
          ) : activeTool === "claude" ? (
            <div className="space-y-4">
              {latestReleases.map((release) => {
                const highlights = getHighlights(release);
                const hasJa = release.highlights_ja && release.highlights_ja.length > 0;
                const hasAnalysis = analysis?.version === release.version;
                const attr = hasAnalysis ? analysis?.attribution : null;
                const actionCount = hasAnalysis ? analysis?.action_items?.length ?? 0 : 0;
                return (
                  <div
                    key={release.version}
                    className="p-4 bg-slate-900 border border-slate-800 rounded-lg"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-bold text-violet-400">
                          {release.version}
                        </span>
                        <span className="text-sm text-slate-500">{release.date}</span>
                        {/* Attribution Badge */}
                        {attr && (
                          <span className={`text-xs px-2 py-0.5 rounded border ${getClassificationStyle(attr.classification)}`}>
                            {attr.classification}
                          </span>
                        )}
                        {attr && (
                          <span className={`text-xs ${getRiskStyle(attr.risk_level)}`}>
                            Risk: {attr.risk_level}
                          </span>
                        )}
                        {!hasJa && lang === "ja" && (
                          <span className="text-xs px-2 py-0.5 bg-slate-700 text-slate-400 rounded">
                            翻訳なし
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        {/* Action Items Count */}
                        <a
                          href="/actions"
                          className="text-xs px-2 py-1 bg-violet-900/50 text-violet-300 rounded hover:bg-violet-800/50"
                        >
                          📋 {actionCount} アクション
                        </a>
                        {release.meanings && release.meanings.length > 0 ? (
                          <a
                            href={`/releases/${release.version}`}
                            className="text-sm text-violet-400 hover:text-violet-300"
                          >
                            詳細 →
                          </a>
                        ) : (
                          <a
                            href={release.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-slate-400 hover:text-slate-200"
                          >
                            GitHub →
                          </a>
                        )}
                      </div>
                    </div>
                    <ul className="text-slate-300 text-sm space-y-1">
                      {highlights.map((h, i) => (
                        <li key={i}>・{h}</li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          ) : activeTool === "codex" ? (
            /* Codex Tab Content */
            <div className="space-y-4">
              {codexImportantReleases.length > 0 ? (
                codexImportantReleases.map((release) => {
                  const highlights = lang === "ja" && release.highlights_ja && release.highlights_ja.length > 0
                    ? release.highlights_ja
                    : release.highlights_en;
                  const hasJa = release.highlights_ja && release.highlights_ja.length > 0;
                  const isRelevant = release.relevance?.applies_to_you ?? false;
                  const hasCodexAnalysis = codexAnalysis?.version === release.version;
                  const codexActionCount = hasCodexAnalysis ? codexAnalysis?.action_items?.length ?? 0 : 0;

                  return (
                    <div
                      key={release.version}
                      className={`p-4 bg-slate-900 border rounded-lg ${isRelevant ? "border-emerald-500/50" : "border-slate-800"}`}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          {isRelevant && (
                            <span className="text-lg" title="あなたの環境に関連あり">🎯</span>
                          )}
                          <span className="text-lg font-bold text-emerald-400">
                            {release.version}
                          </span>
                          <span className="text-sm text-slate-500">{release.date}</span>
                          <span className={`text-xs px-2 py-0.5 rounded border ${getImportanceStyle(release.importance.level)}`}>
                            {release.importance.level}
                          </span>
                          {release.importance.tags.map((tag) => (
                            <span key={tag} className="text-xs px-2 py-0.5 bg-slate-700 text-slate-300 rounded">
                              {tag}
                            </span>
                          ))}
                          {!hasJa && lang === "ja" && (
                            <span className="text-xs px-2 py-0.5 bg-slate-700 text-slate-400 rounded">
                              翻訳なし
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3">
                          <a
                            href={`/releases/${release.version}`}
                            className="text-xs px-2 py-1 bg-emerald-900/50 text-emerald-300 rounded hover:bg-emerald-800/50"
                          >
                            📋 {codexActionCount} アクション
                          </a>
                          <a
                            href={release.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-slate-400 hover:text-slate-200"
                          >
                            GitHub →
                          </a>
                        </div>
                      </div>

                      {/* Highlights リスト（カテゴリ別） */}
                      {release.categorized_highlights && release.categorized_highlights.length > 0 ? (
                        <div className="space-y-3">
                          {Object.entries(CODEX_CATEGORY_CONFIG)
                            .sort(([, a], [, b]) => a.order - b.order)
                            .map(([categoryKey, config]) => {
                              // カテゴリに属するアイテムのインデックスを取得
                              const itemsWithIndex = release.categorized_highlights!
                                .map((h, idx) => ({ ...h, originalIndex: idx }))
                                .filter((h) => h.category === categoryKey);
                              if (itemsWithIndex.length === 0) return null;

                              return (
                                <div key={categoryKey}>
                                  <h4 className={`text-sm font-semibold mb-1 ${config.color}`}>
                                    {config.label}
                                  </h4>
                                  <ul className="text-slate-300 text-sm space-y-0.5 pl-2">
                                    {itemsWithIndex.map((item) => {
                                      // 日本語があれば日本語を表示
                                      const displayText = lang === "ja" && hasJa && release.highlights_ja?.[item.originalIndex]
                                        ? release.highlights_ja[item.originalIndex]
                                        : item.text;
                                      return (
                                        <li key={item.originalIndex}>・{displayText}</li>
                                      );
                                    })}
                                  </ul>
                                </div>
                              );
                            })}
                        </div>
                      ) : (
                        <ul className="text-slate-300 text-sm space-y-1">
                          {highlights.map((h, idx) => (
                            <li key={idx}>・{h}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg">
                  <p className="text-slate-400 text-sm">重要な更新なし（最新: {codexLatestVersion}）</p>
                </div>
              )}
              <p className="text-xs text-slate-500 mt-2">
                ※ 軽量監視: 重要な変更（security / breaking / model）のみ表示
              </p>
            </div>
          ) : activeTool === "articles" ? (
            /* Articles Tab Content */
            <div className="space-y-4">
              {articleData && articleData.evaluations.length > 0 ? (
                <>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm text-slate-400">
                      {articleData.total} 件評価済み（LLM: {articleData.llm_evaluated}, FB: {articleData.fallback_used}）
                      {articleData.evaluated_at && ` | ${new Date(articleData.evaluated_at).toLocaleString("ja-JP")}`}
                    </p>
                    <button
                      onClick={handleExportApproved}
                      className="px-3 py-1 text-sm bg-sky-900/50 text-sky-300 rounded hover:bg-sky-800/50 border border-sky-700"
                    >
                      承認済みエクスポート
                    </button>
                  </div>
                  {articleData.evaluations
                    .sort((a, b) => b.relevance - a.relevance || b.actionability - a.actionability)
                    .map((article) => {
                      const decision = articleDecisions[article.url] || "pending";
                      return (
                        <div
                          key={article.url}
                          className={`p-4 bg-slate-900 border rounded-lg ${
                            decision === "approve"
                              ? "border-green-500/50"
                              : decision === "reject"
                                ? "border-red-500/30 opacity-60"
                                : "border-slate-800"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-3">
                              <span className={`text-sm font-bold ${
                                article.recommended_action === "adopt" ? "text-green-400" :
                                article.recommended_action === "watch" ? "text-yellow-400" : "text-slate-500"
                              }`}>
                                {article.recommended_action === "adopt" ? "採用" :
                                 article.recommended_action === "watch" ? "注視" : "スキップ"}
                              </span>
                              <span className="text-xs px-2 py-0.5 bg-slate-700 text-slate-300 rounded">
                                関連性: {article.relevance}/5
                              </span>
                              <span className="text-xs px-2 py-0.5 bg-slate-700 text-slate-300 rounded">
                                実用性: {article.actionability}/5
                              </span>
                              {article.source_topic && (
                                <span className="text-xs px-2 py-0.5 bg-sky-900/50 text-sky-300 rounded">
                                  {article.source_topic}
                                </span>
                              )}
                              <span className="text-xs text-slate-500">
                                {article.evaluation_source === "llm" ? "LLM" : "FB"}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => handleArticleDecision(article.url, decision === "approve" ? "pending" : "approve")}
                                className={`px-3 py-1 text-xs rounded transition-colors ${
                                  decision === "approve"
                                    ? "bg-green-600 text-white"
                                    : "bg-slate-700 text-slate-300 hover:bg-green-700"
                                }`}
                              >
                                承認
                              </button>
                              <button
                                onClick={() => handleArticleDecision(article.url, decision === "reject" ? "pending" : "reject")}
                                className={`px-3 py-1 text-xs rounded transition-colors ${
                                  decision === "reject"
                                    ? "bg-red-600 text-white"
                                    : "bg-slate-700 text-slate-300 hover:bg-red-700"
                                }`}
                              >
                                却下
                              </button>
                            </div>
                          </div>
                          <a
                            href={article.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sky-400 hover:text-sky-300 font-medium"
                          >
                            {article.title}
                          </a>
                          <p className="text-slate-400 text-sm mt-1">{article.summary_ja}</p>
                        </div>
                      );
                    })}
                </>
              ) : (
                <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg">
                  <p className="text-slate-400 text-sm">
                    記事候補なし。<code className="text-sky-300">python -m collectors.cli evaluate-articles --days 7 --output ../frontend/public/data/article_candidates.json</code> で生成してください。
                  </p>
                </div>
              )}
            </div>
          ) : null}
        </section>

        {/* Notable Features - Claude Code only */}
        {activeTool === "claude" && (
          <section className="mb-12">
            <h2 className="text-xl font-semibold mb-4">注目機能（2.1.x / 2.0.x）</h2>
            <div className="grid md:grid-cols-2 gap-4">
              {features.map((f) => (
                <div
                  key={f.title}
                  className="p-4 bg-slate-900 border border-slate-800 rounded-lg"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs px-2 py-1 bg-violet-900/50 text-violet-300 rounded">
                      {f.version}
                    </span>
                    <span className="font-semibold">{f.title}</span>
                  </div>
                  <p className="text-slate-400 text-sm">{f.desc}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Stats - Tool specific */}
        <section className="mb-12">
          <h2 className="text-xl font-semibold mb-4">統計</h2>
          {activeTool === "claude" ? (
            <div className="grid grid-cols-4 gap-4">
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
                <div className="text-3xl font-bold text-violet-400">
                  {data?.releases.length ?? "..."}
                </div>
                <div className="text-slate-400 text-sm">取得リリース数</div>
              </div>
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
                <div className="text-3xl font-bold text-violet-400">{latestVersion}</div>
                <div className="text-slate-400 text-sm">最新バージョン</div>
              </div>
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
                <div className="text-3xl font-bold text-amber-400">
                  {analysis?.action_items?.length ?? 0}
                </div>
                <div className="text-slate-400 text-sm">アクション待ち</div>
              </div>
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
                <div className={`text-3xl font-bold ${analysis?.attribution ? getClassificationStyle(analysis.attribution.classification).split(' ')[1] : 'text-slate-500'}`}>
                  {analysis?.attribution?.classification ?? "-"}
                </div>
                <div className="text-slate-400 text-sm">分類</div>
              </div>
            </div>
          ) : activeTool === "codex" ? (
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
                <div className="text-3xl font-bold text-emerald-400">
                  {codexData?.releases.filter(r => !r.prerelease).length ?? "..."}
                </div>
                <div className="text-slate-400 text-sm">取得リリース数</div>
              </div>
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
                <div className="text-3xl font-bold text-emerald-400">{codexLatestVersion}</div>
                <div className="text-slate-400 text-sm">最新バージョン</div>
              </div>
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
                <div className="text-3xl font-bold text-red-400">
                  {codexImportantReleases.length}
                </div>
                <div className="text-slate-400 text-sm">重要な更新</div>
              </div>
            </div>
          ) : (
            /* Articles Stats */
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
                <div className="text-3xl font-bold text-sky-400">
                  {articleData?.evaluations.length ?? 0}
                </div>
                <div className="text-slate-400 text-sm">候補記事数</div>
              </div>
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
                <div className="text-3xl font-bold text-green-400">
                  {Object.values(articleDecisions).filter(d => d === "approve").length}
                </div>
                <div className="text-slate-400 text-sm">承認済み</div>
              </div>
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
                <div className="text-3xl font-bold text-amber-400">
                  {articleData?.evaluations.filter(e => e.recommended_action === "adopt").length ?? 0}
                </div>
                <div className="text-slate-400 text-sm">AI 採用推奨</div>
              </div>
            </div>
          )}
        </section>

        {/* Monitoring Status */}
        <section className="mb-12">
          <h2 className="text-xl font-semibold mb-4">監視設定</h2>
          <div className="grid md:grid-cols-3 gap-4">
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></span>
                <span className="font-semibold text-violet-400">Claude Code</span>
                <span className="text-xs px-2 py-0.5 bg-violet-900/50 text-violet-300 rounded">フル分析</span>
              </div>
              <ul className="text-slate-400 text-sm space-y-1">
                <li>・GitHub Releases を定期チェック</li>
                <li>・AI 分析で影響評価・アクション生成</li>
                <li>・collectors/claude_code/</li>
              </ul>
            </div>
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></span>
                <span className="font-semibold text-emerald-400">Codex</span>
                <span className="text-xs px-2 py-0.5 bg-emerald-900/50 text-emerald-300 rounded">軽量監視</span>
              </div>
              <ul className="text-slate-400 text-sm space-y-1">
                <li>・GitHub Releases を定期チェック</li>
                <li>・重要変更（security/breaking）のみ検出</li>
                <li>・collectors/codex/</li>
              </ul>
            </div>
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-3 h-3 bg-sky-500 rounded-full animate-pulse"></span>
                <span className="font-semibold text-sky-400">Zenn 記事</span>
                <span className="text-xs px-2 py-0.5 bg-sky-900/50 text-sky-300 rounded">段階フィルター</span>
              </div>
              <ul className="text-slate-400 text-sm space-y-1">
                <li>・Zenn RSS から AI 関連記事を収集</li>
                <li>・LLM で転用可能性を自動評価</li>
                <li>・collectors/cli.py evaluate-articles</li>
              </ul>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="text-center text-slate-500 text-sm">
          <p>AI Update Radar - 自分用ダッシュボード</p>
        </footer>
      </div>
    </main>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">Loading...</div>}>
      <HomeContent />
    </Suspense>
  );
}
