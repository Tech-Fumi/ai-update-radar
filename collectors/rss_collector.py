"""
RSS/Atom フィード収集
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from time import mktime
from typing import Optional

import feedparser
import httpx
import yaml

from collectors.models import Category, CollectedEntry, CollectionResult, SourceType


class RSSCollector:
    """RSS/Atom フィードを収集"""

    def __init__(
        self,
        sources_dir: Path,
        cache_dir: Path,
        keywords_path: Optional[Path] = None,
    ):
        self.sources_dir = sources_dir
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # キーワード読み込み
        self.keywords = self._load_keywords(keywords_path)

    def _load_keywords(self, keywords_path: Optional[Path]) -> dict:
        """keywords.yaml を読み込み"""
        if keywords_path and keywords_path.exists():
            with open(keywords_path) as f:
                return yaml.safe_load(f) or {}
        return {}

    def _get_cache_path(self, source_name: str) -> Path:
        """キャッシュファイルのパスを取得"""
        return self.cache_dir / f"{source_name}_rss_cache.json"

    def _load_cache(self, source_name: str) -> set[str]:
        """キャッシュされた URL を読み込み"""
        cache_path = self._get_cache_path(source_name)
        if cache_path.exists():
            with open(cache_path) as f:
                data = json.load(f)
                return set(data.get("seen_urls", []))
        return set()

    def _save_cache(self, source_name: str, seen_urls: set[str]) -> None:
        """キャッシュを保存"""
        cache_path = self._get_cache_path(source_name)
        with open(cache_path, "w") as f:
            json.dump(
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "seen_urls": list(seen_urls),
                },
                f,
                indent=2,
            )

    def _classify_entry(self, title: str, summary: str) -> tuple[list[Category], list[str]]:
        """エントリをカテゴリ分類し、マッチしたキーワードを返す"""
        categories = []
        matched_keywords = []
        text = f"{title} {summary}".lower()

        if not self.keywords.get("categories"):
            return [Category.OTHER], []

        for cat_name, cat_data in self.keywords["categories"].items():
            if cat_name == "other":
                continue

            # 各サブカテゴリのキーワードをチェック
            for sub_keywords in cat_data.values():
                if isinstance(sub_keywords, list):
                    for kw in sub_keywords:
                        if kw.lower() in text:
                            matched_keywords.append(kw)
                            if cat_name in Category._value2member_map_:
                                cat = Category(cat_name)
                            else:
                                cat = Category.OTHER
                            if cat not in categories:
                                categories.append(cat)

        # 無視キーワードチェック
        ignore_keywords = self.keywords.get("ignore", {}).get("keywords", [])
        for kw in ignore_keywords:
            if kw.lower() in text:
                # 無視対象の場合は OTHER にダウングレード
                return [Category.OTHER], matched_keywords

        return categories if categories else [Category.OTHER], matched_keywords

    def collect_feed(
        self,
        source_name: str,
        feed_url: str,
        since: Optional[datetime] = None,
    ) -> CollectionResult:
        """単一のフィードを収集"""
        result = CollectionResult(
            source_name=source_name,
            source_type=SourceType.RSS,
            collected_at=datetime.now(timezone.utc),
        )

        try:
            # フィード取得
            response = httpx.get(feed_url, timeout=30, follow_redirects=True)
            response.raise_for_status()

            feed = feedparser.parse(response.text)

            if feed.bozo and not feed.entries:
                result.errors.append(f"Feed parse error: {feed.bozo_exception}")
                result.success = False
                return result

            # キャッシュ読み込み
            seen_urls = self._load_cache(source_name)

            for entry in feed.entries:
                url = entry.get("link", "")

                # 既に見たエントリはスキップ
                if url in seen_urls:
                    continue

                # 日付パース
                published_at = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published_at = datetime.fromtimestamp(
                        mktime(entry.published_parsed), tz=timezone.utc
                    )
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published_at = datetime.fromtimestamp(
                        mktime(entry.updated_parsed), tz=timezone.utc
                    )

                # since フィルタ
                if since and published_at and published_at < since:
                    continue

                # サマリ取得
                summary = entry.get("summary", "")
                if hasattr(entry, "content") and entry.content:
                    summary = entry.content[0].get("value", summary)

                # カテゴリ分類
                title = entry.get("title", "")
                categories, keywords = self._classify_entry(title, summary)

                collected = CollectedEntry(
                    title=title,
                    url=url,
                    source_name=source_name,
                    source_type=SourceType.RSS,
                    published_at=published_at,
                    summary=summary[:500] if summary else "",
                    categories=categories,
                    keywords=keywords,
                )
                result.entries.append(collected)
                seen_urls.add(url)

            # キャッシュ保存
            self._save_cache(source_name, seen_urls)

        except httpx.HTTPError as e:
            result.errors.append(f"HTTP error: {e}")
            result.success = False
        except Exception as e:
            result.errors.append(f"Unexpected error: {e}")
            result.success = False

        return result

    def collect_all(self, since: Optional[datetime] = None) -> list[CollectionResult]:
        """providers.yaml の全フィードを収集"""
        results = []

        providers_path = self.sources_dir / "providers.yaml"
        if not providers_path.exists():
            return results

        with open(providers_path) as f:
            providers = yaml.safe_load(f) or {}

        for provider_id, provider_data in providers.get("providers", {}).items():
            for source in provider_data.get("sources", []):
                if source.get("type") == "blog" and source.get("rss"):
                    result = self.collect_feed(
                        source_name=f"{provider_id}-blog",
                        feed_url=source["rss"],
                        since=since,
                    )
                    results.append(result)

        return results


def main():
    """CLI エントリポイント"""
    import argparse

    from rich.console import Console
    from rich.table import Table

    parser = argparse.ArgumentParser(description="RSS フィード収集")
    parser.add_argument("--source", help="特定のソースのみ収集")
    parser.add_argument("--days", type=int, default=7, help="過去N日分を収集")
    parser.add_argument("--json", action="store_true", help="JSON 出力")
    args = parser.parse_args()

    console = Console()

    # パス設定
    base_dir = Path(__file__).parent.parent
    sources_dir = base_dir / "sources"
    cache_dir = base_dir / ".private" / "cache"
    keywords_path = sources_dir / "keywords.yaml"

    collector = RSSCollector(
        sources_dir=sources_dir,
        cache_dir=cache_dir,
        keywords_path=keywords_path,
    )

    # 収集
    since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    since = since - timedelta(days=args.days)

    if args.source:
        providers_path = sources_dir / "providers.yaml"
        with open(providers_path) as f:
            providers = yaml.safe_load(f) or {}

        provider_data = providers.get("providers", {}).get(args.source, {})
        for source in provider_data.get("sources", []):
            if source.get("type") == "blog" and source.get("rss"):
                result = collector.collect_feed(
                    source_name=f"{args.source}-blog",
                    feed_url=source["rss"],
                    since=since,
                )
                results = [result]
                break
        else:
            console.print(f"[red]Source not found: {args.source}[/red]")
            return
    else:
        results = collector.collect_all(since=since)

    # 出力
    if args.json:
        output = [r.to_dict() for r in results]
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        for result in results:
            if result.entries:
                table = Table(title=f"{result.source_name} ({len(result.entries)} entries)")
                table.add_column("Date", style="dim")
                table.add_column("Title")
                table.add_column("Category")
                table.add_column("Keywords", style="cyan")

                for entry in result.entries[:10]:  # 最大10件
                    date_str = entry.published_at.strftime("%m/%d") if entry.published_at else "-"
                    cats = ", ".join(c.value for c in entry.categories)
                    kws = ", ".join(entry.keywords[:3])
                    table.add_row(date_str, entry.title[:50], cats, kws)

                console.print(table)
                console.print()

            if result.errors:
                for err in result.errors:
                    console.print(f"[red]Error: {err}[/red]")


if __name__ == "__main__":
    main()
