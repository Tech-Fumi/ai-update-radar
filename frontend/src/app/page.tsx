// Claude Code の最新リリース情報を表示するページ（自分用）
const GITHUB_RELEASES_URL = "https://github.com/anthropics/claude-code/releases";
const CHANGELOG_URL = "https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md";

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
];

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-5xl mx-auto px-4 py-12">
        {/* Header */}
        <header className="mb-12">
          <h1 className="text-4xl font-bold mb-2">
            Claude Code Update Radar
          </h1>
          <p className="text-slate-400">
            Claude Code の最新アップデートを追跡する自分用ダッシュボード
          </p>
        </header>

        {/* Quick Links */}
        <section className="mb-12">
          <h2 className="text-xl font-semibold mb-4">クイックリンク</h2>
          <div className="flex flex-wrap gap-3">
            {links.map((link) => (
              <a
                key={link.label}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 transition-colors"
              >
                {link.label} →
              </a>
            ))}
          </div>
        </section>

        {/* Recent Features */}
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

        {/* Stats */}
        <section className="mb-12">
          <h2 className="text-xl font-semibold mb-4">2025年の実績</h2>
          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
              <div className="text-3xl font-bold text-violet-400">176</div>
              <div className="text-slate-400 text-sm">アップデート回数</div>
            </div>
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
              <div className="text-3xl font-bold text-violet-400">1,096</div>
              <div className="text-slate-400 text-sm">コミット（2.1.0）</div>
            </div>
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg text-center">
              <div className="text-3xl font-bold text-violet-400">2.1.4</div>
              <div className="text-slate-400 text-sm">最新バージョン</div>
            </div>
          </div>
        </section>

        {/* Monitoring Status */}
        <section className="mb-12">
          <h2 className="text-xl font-semibold mb-4">監視設定</h2>
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></span>
              <span className="font-semibold">監視中</span>
            </div>
            <ul className="text-slate-400 text-sm space-y-1">
              <li>• GitHub Releases RSS を 2時間ごとにチェック</li>
              <li>• 新しいリリースは Discord #claude-code-updates に通知</li>
              <li>• スクリプト: ai-update-radar/collectors/claude_code/monitor.py</li>
            </ul>
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
