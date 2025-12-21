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

## 実装予定

- [ ] rss_collector.py
- [ ] github_collector.py
- [ ] page_diff_collector.py
- [ ] unified_runner.py
