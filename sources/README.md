# Sources - 監視対象定義

AIの変化を検知するための情報源を定義する。

## 監視カテゴリ

### 1. 公式ブログ・リリースノート

| プロバイダー | URL | 監視頻度 |
|-------------|-----|---------|
| OpenAI | https://openai.com/blog | 日次 |
| Anthropic | https://www.anthropic.com/news | 日次 |
| Google AI | https://ai.google/discover/latest-news | 日次 |
| Meta AI | https://ai.meta.com/blog | 週次 |
| Mistral | https://mistral.ai/news | 週次 |

### 2. GitHub Releases

| リポジトリ | 監視対象 |
|-----------|---------|
| openai/openai-python | SDK更新 |
| anthropics/anthropic-sdk-python | SDK更新 |
| langchain-ai/langchain | フレームワーク |
| microsoft/autogen | Agent Framework |
| modelcontextprotocol/servers | MCP |

### 3. 価格ページ

| サービス | URL | 監視ポイント |
|---------|-----|-------------|
| OpenAI API | https://openai.com/api/pricing | トークン単価、新モデル |
| Anthropic API | https://www.anthropic.com/pricing | トークン単価、新機能 |
| Vercel AI | https://vercel.com/pricing | AI機能追加 |

### 4. 技術ドキュメント

| ドキュメント | 監視ポイント |
|-------------|-------------|
| OpenAI API Docs | 新エンドポイント、パラメータ変更 |
| Anthropic Docs | 新機能、制限変更 |
| Claude Code | 新コマンド、新機能 |

## 検知すべき変化

### 能力変化（Capability）

- [ ] 新モデルのリリース
- [ ] 既存モデルの能力向上
- [ ] 新機能の追加（Vision, Tools, Memory等）
- [ ] Agent機能の拡張
- [ ] IDE/Browser統合

### 制限解除（Constraint Removal）

- [ ] コンテキスト長の拡張
- [ ] レート制限の緩和
- [ ] 出力長の拡張
- [ ] 新リージョンの追加
- [ ] 利用規約の変更

### 価格変化（Pricing）

- [ ] 料金改定（値下げ/値上げ）
- [ ] 新プランの追加
- [ ] 無料枠の変更
- [ ] 従量課金モデルの変更

## ファイル構成

```
sources/
├── README.md           # このファイル
├── providers.yaml      # プロバイダー定義
├── repositories.yaml   # GitHub監視対象
├── pricing.yaml        # 価格ページ定義
└── keywords.yaml       # 検知キーワード
```
