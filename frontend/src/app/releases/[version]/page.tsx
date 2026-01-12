import Link from "next/link";
import { notFound } from "next/navigation";

// リリースデータ（日本語 + ユーザー向け解説）
const releases: Record<string, {
  version: string;
  date: string;
  summary: string;
  changes: {
    category: string;
    items: {
      title: string;
      meaning: string;
    }[]
  }[];
}> = {
  "v2.1.4": {
    version: "v2.1.4",
    date: "2026-01-11",
    summary: "バックグラウンドタスクの制御と OAuth の安定性向上",
    changes: [
      {
        category: "追加",
        items: [
          {
            title: "環境変数 CLAUDE_CODE_DISABLE_BACKGROUND_TASKS を追加",
            meaning: "バックグラウンドタスク機能（自動バックグラウンド化、Ctrl+B）が邪魔な場合、この環境変数で完全に無効化できます。シンプルに使いたい人向け。",
          },
        ],
      },
      {
        category: "修正",
        items: [
          {
            title: "OAuth トークン期限切れ時の自動リトライ",
            meaning: "長時間使っていると「Help improve Claude」設定の取得が失敗することがありましたが、自動でリフレッシュ・リトライするようになりました。セッション中の認証エラーが減ります。",
          },
        ],
      },
    ],
  },
  "v2.1.3": {
    version: "v2.1.3",
    date: "2026-01-10",
    summary: "スラッシュコマンドと Skills の統合、VSCode 拡張の改善",
    changes: [
      {
        category: "追加",
        items: [
          {
            title: "スラッシュコマンドと Skills を統合",
            meaning: "以前は「スラッシュコマンド」と「Skills」が別々の概念でしたが、統合されて1つになりました。覚えることが減ってシンプルに。動作は変わりません。",
          },
          {
            title: "/config にリリースチャンネル切り替えを追加",
            meaning: "stable（安定版）と latest（最新版）を /config から簡単に切り替えられるようになりました。最新機能を試したい時に便利。",
          },
          {
            title: "到達不能なパーミッションルールの検出",
            meaning: "設定したパーミッションルールが実際には効かない（到達不能）場合、/doctor や保存時に警告が出るようになりました。設定ミスに気づきやすくなります。",
          },
        ],
      },
      {
        category: "修正",
        items: [
          {
            title: "/clear 後もプランファイルが残る問題を修正",
            meaning: "会話をクリアしても以前のプランが残っていた問題が解消。クリア後は完全にリセットされます。",
          },
          {
            title: "サブエージェントが間違ったモデルを使用する問題を修正",
            meaning: "会話が長くなってコンパクションが発生した時、サブエージェントが意図しないモデルを使う問題が修正されました。",
          },
          {
            title: "ホームディレクトリから実行時の trust 問題を修正",
            meaning: "ホームディレクトリから Claude Code を実行した場合、trust を承認しても Hooks などが有効にならない問題が解消されました。",
          },
        ],
      },
      {
        category: "変更",
        items: [
          {
            title: "Tool Hook のタイムアウトを 60秒 → 10分 に延長",
            meaning: "Hook で重い処理を実行している場合、60秒でタイムアウトしていましたが、10分まで待つようになりました。CI/CD 連携など時間のかかる Hook が使いやすくなります。",
          },
          {
            title: "[VSCode] パーミッション保存先の選択が可能に",
            meaning: "VSCode 拡張で、パーミッション設定をどこに保存するか選べるようになりました。「このプロジェクトだけ」「全プロジェクト」「チーム共有」「セッションのみ」から選択可能。",
          },
        ],
      },
    ],
  },
  "v2.1.2": {
    version: "v2.1.2",
    date: "2026-01-09",
    summary: "画像のコンテキスト理解向上、Windows サポート強化、セキュリティ修正",
    changes: [
      {
        category: "追加",
        items: [
          {
            title: "ドラッグした画像にソースパスメタデータを追加",
            meaning: "画像をターミナルにドラッグした時、「その画像がどこから来たか（ファイルパス）」の情報が Claude に渡るようになりました。画像の読み込み自体は以前からできましたが、今回の変更で Claude が「このスクリーンショットは〇〇ディレクトリにあるから、関連コードはここでしょう」と推測できるようになります。",
          },
          {
            title: "ファイルパスがクリック可能なリンクに（OSC 8 対応ターミナル）",
            meaning: "iTerm 等の対応ターミナルで、ツール出力に含まれるファイルパスをクリックするだけでそのファイルを開けるようになりました。パスをコピペする手間が省けます。",
          },
          {
            title: "Windows Package Manager（winget）によるインストールをサポート",
            meaning: "Windows ユーザーは winget install claude-code でインストールできるようになりました。アップデート手順も自動で案内されます。",
          },
          {
            title: "プランモードで Shift+Tab ショートカットを追加",
            meaning: "プランモードで「自動承認編集」オプションを素早く選べるようになりました。毎回マウスで選択する手間が省けます。",
          },
        ],
      },
      {
        category: "セキュリティ修正",
        items: [
          {
            title: "コマンドインジェクション脆弱性を修正",
            meaning: "Bash コマンド処理で、不正な入力により意図しないコマンドが実行される可能性がありました。このバージョンへのアップデートを推奨します。",
          },
        ],
      },
      {
        category: "修正",
        items: [
          {
            title: "長時間セッションでのメモリリークを修正",
            meaning: "tree-sitter のパースツリーが解放されず、長時間使っているとメモリ使用量が増え続ける問題が解消されました。長時間作業する人に朗報です。",
          },
          {
            title: "CLAUDE.md の @include でバイナリファイルが含まれる問題を修正",
            meaning: "@include で画像や PDF を誤って含めてしまった場合、以前はメモリに読み込まれていましたが、今は正しくスキップされます。",
          },
        ],
      },
      {
        category: "改善",
        items: [
          {
            title: "通常の開発ワークフローを中リスク扱いしないよう改善",
            meaning: "git fetch/rebase、npm install、テスト実行、PR 作成などの一般的な操作が「中リスク」と警告されなくなりました。毎回の確認が減って快適に。",
          },
        ],
      },
      {
        category: "変更",
        items: [
          {
            title: "大きな出力をディスクに保存するよう変更",
            meaning: "以前は大きな Bash 出力やツール出力が切り詰められていましたが、ディスクに保存されるようになりました。Claude が全内容を読めるようになり、長いログやビルド出力も正しく処理できます。",
          },
        ],
      },
    ],
  },
};

export function generateStaticParams() {
  return Object.keys(releases).map((version) => ({ version }));
}

export default async function ReleasePage({
  params,
}: {
  params: Promise<{ version: string }>;
}) {
  const { version } = await params;
  const release = releases[version];

  if (!release) {
    notFound();
  }

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
          <p className="text-slate-300 text-lg">{release.summary}</p>
          <a
            href={`https://github.com/anthropics/claude-code/releases/tag/${release.version}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-violet-400 hover:text-violet-300 text-sm mt-3 inline-block"
          >
            GitHub で原文を見る →
          </a>
        </header>

        {/* Changes */}
        <div className="space-y-8">
          {release.changes.map((section) => (
            <section key={section.category}>
              <h2 className="text-xl font-semibold mb-4 text-violet-400">
                {section.category}
              </h2>
              <div className="space-y-4">
                {section.items.map((item, i) => (
                  <div
                    key={i}
                    className="p-4 bg-slate-900 border border-slate-800 rounded-lg"
                  >
                    <h3 className="font-semibold text-slate-100 mb-2">
                      {item.title}
                    </h3>
                    <p className="text-slate-400 text-sm leading-relaxed">
                      {item.meaning}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>

        {/* Footer */}
        <footer className="mt-12 pt-8 border-t border-slate-800 text-center text-slate-500 text-sm">
          <p>AI Update Radar - 自分用ダッシュボード</p>
        </footer>
      </div>
    </main>
  );
}
