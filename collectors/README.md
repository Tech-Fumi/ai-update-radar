# Collectors - 収集スクリプト

監視対象から情報を自動収集するスクリプト群。

## 設計方針

1. **軽量**: 依存を最小限に
2. **冪等**: 何度実行しても同じ結果
3. **ログ重視**: 取得履歴を必ず記録
4. **失敗許容**: 一部失敗しても継続

## コレクター種別

### 1. RSS/Atom Collector

ブログ・ニュースフィードを収集。

```python
# 例: rss_collector.py
def collect_rss(feed_url: str) -> List[Entry]:
    """RSSフィードから新着を取得"""
    pass
```

### 2. GitHub Release Collector

GitHub Releases APIを使用。

```python
# 例: github_collector.py
def collect_releases(repo: str, since: datetime) -> List[Release]:
    """指定日以降のリリースを取得"""
    pass
```

### 3. Page Diff Collector

価格ページ等の変化を検知。

```python
# 例: page_diff_collector.py
def detect_changes(url: str, previous_hash: str) -> Optional[Diff]:
    """ページ内容の変化を検知"""
    pass
```

### 4. API Changelog Collector

公式ドキュメントの更新を検知。

## 出力フォーマット

すべてのコレクターは以下の形式で出力：

```json
{
  "collected_at": "2025-12-21T10:00:00Z",
  "source": "openai-blog",
  "entries": [
    {
      "title": "...",
      "url": "...",
      "published_at": "...",
      "category": "capability|constraint|pricing|other",
      "keywords": ["..."]
    }
  ]
}
```

## 実行方法

```bash
# 全ソースを収集
python collectors/run_all.py

# 特定ソースのみ
python collectors/rss_collector.py --source openai-blog
```

## Codex Collector

OpenAI Codex のリリース情報を収集し、関連性を評価する。

### 実行方法

```bash
cd collectors/codex
source ../claude_code/venv/bin/activate

# リリース収集 + 関連性評価
python monitor.py

# テスト実行
python test_relevance.py

# JSON 整合性チェック
python validate_json.py
```

### トラブルシューティング：誤爆対応

「影響あり」に誤って分類された場合の対応手順:

1. **再現テストを追加**
   ```bash
   # test_relevance.py に誤爆ケースを追加
   # → CI で再発を自動検知
   ```

2. **分類理由を確認**
   ```python
   # monitor.py の出力で classifications を確認
   # {idx: {subtype, reason, dest}} で判定理由が追える
   ```

3. **JSON 整合性を確認**
   ```bash
   python validate_json.py
   # インデックス範囲外参照などを検出
   ```

### 関連ファイル

| ファイル | 役割 |
|----------|------|
| `monitor.py` | 収集 + 関連性評価 |
| `test_relevance.py` | 誤爆検知のゴールデンテスト (9ケース) |
| `validate_json.py` | 生成物 JSON の整合性チェック |

---

## 実装予定

- [ ] rss_collector.py
- [ ] github_collector.py
- [ ] page_diff_collector.py
- [ ] unified_runner.py
