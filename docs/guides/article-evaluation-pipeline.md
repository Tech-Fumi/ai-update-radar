# 記事評価パイプライン

Zenn 記事を自動収集 → LLM 評価 → 人間レビュー → 通知するパイプライン。

## アーキテクチャ

```
[Zenn RSS] → ソフトフィルター → [LLM評価] → article_candidates.json → [承認UI] → [通知]
                                    ↑                                      ↑           ↑
                              MCP gateway                            フロントエンド   CLI
                              /call endpoint                         /actions        notify-articles
```

## 自動化範囲

| ステップ | 方式 | 自動/手動 |
|---------|------|:---------:|
| Zenn 記事収集 + ソフトフィルター | `evaluate-articles` CLI | 自動（cron） |
| LLM 評価（relevance, actionability, summary） | MCP gateway → GPT | 自動（cron） |
| `article_candidates.json` 出力 | `update-article-candidates.sh` | 自動（cron） |
| 人間レビュー・承認 | フロントエンド `/actions` ページ | 手動 |
| 承認済み記事の通知 | `notify-articles` CLI | 手動 |

## スケジュール

- **毎週火曜 9:00**: `update-article-candidates.sh --days 7` を cron で実行
- ログ: `.private/logs/cron_article_update.log`

## 手動実行

```bash
# デフォルト（7日分）
./scripts/update-article-candidates.sh

# 14日分
./scripts/update-article-candidates.sh --days 14

# CLI 直接実行
python -m collectors.cli evaluate-articles --days 7
```

## 依存

| 依存 | 設定場所 |
|------|---------|
| `SEND_CONSULTATION_URL` | `.env`（MCP gateway の `/call` エンドポイント） |
| MCP gateway | `http://100.110.236.96:8000/call` |
| Python venv | `.venv/`（自動アクティベート） |

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `collectors/zenn_collector.py` | Zenn RSS 収集 + ソフトフィルター |
| `evaluators/article_evaluator.py` | LLM バッチ評価（5件単位 + リトライ + フォールバック） |
| `collectors/cli.py` | `evaluate-articles` / `notify-articles` CLI コマンド |
| `scripts/update-article-candidates.sh` | 定期実行用シェルスクリプト |
| `frontend/src/app/actions/page.tsx` | 記事承認 UI |
| `frontend/public/data/article_candidates.json` | 評価結果（フロントエンド表示用） |

## LLM 評価の詳細

- **バッチサイズ**: 5件ずつ
- **リトライ**: 失敗時1回リトライ、それでも失敗ならフォールバック
- **フォールバック**: ソフトフィルタースコアに基づく簡易評価（LLM 不要）
- **評価項目**: relevance（1-5）、actionability（1-5）、summary_ja、recommended_action（adopt/watch/skip）

## gateway レスポンス処理

MCP gateway の `/call` レスポンスには consultation ラッパーが含まれる:
1. `structuredContent.result` から生テキストを取得
2. `【ChatGPT の回答】` マーカー以降を抽出
3. 末尾の `---\nModel:...` を除去
4. GPT の JSON 回答のみを `article_evaluator.py` に渡す
