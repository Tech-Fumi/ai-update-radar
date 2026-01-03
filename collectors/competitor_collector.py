"""
競合分析コレクター

WebSearch を使用して競合情報を収集
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from collectors.models import Category, CollectedEntry, CollectionResult, SourceType


class CompetitorCollector:
    """競合・トレンド情報を WebSearch で収集"""

    def __init__(
        self,
        sources_dir: Path,
        output_dir: Path,
        web_search_func: Optional[callable] = None,
    ):
        """
        Args:
            sources_dir: sources/ ディレクトリ
            output_dir: 出力先（.private/marketing/competitors/）
            web_search_func: WebSearch 関数（MCP経由で注入）
        """
        self.sources_dir = sources_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.web_search_func = web_search_func
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """competitors.yaml を読み込み"""
        config_path = self.sources_dir / "competitors.yaml"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def _get_cache_path(self) -> Path:
        """キャッシュファイルのパス"""
        return self.output_dir / "competitor_cache.json"

    def _load_cache(self) -> dict:
        """キャッシュを読み込み"""
        cache_path = self._get_cache_path()
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                return json.load(f)
        return {"seen_urls": [], "last_run": None}

    def _save_cache(self, cache: dict) -> None:
        """キャッシュを保存"""
        cache_path = self._get_cache_path()
        cache["last_run"] = datetime.now(timezone.utc).isoformat()
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)

    def _is_excluded(self, text: str) -> bool:
        """除外キーワードに該当するかチェック"""
        exclude_keywords = self.config.get("exclude_keywords", [])
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in exclude_keywords)

    def collect_trends(self) -> CollectionResult:
        """
        トレンドキーワードで検索して収集

        Returns:
            CollectionResult: 収集結果
        """
        entries = []
        errors = []

        if not self.web_search_func:
            return CollectionResult(
                source_name="competitor_trends",
                source_type=SourceType.WEB_SEARCH,
                entries=[],
                errors=["WebSearch 関数が設定されていません"],
            )

        queries = self.config.get("search_queries", {}).get("trends", [])
        cache = self._load_cache()
        seen_urls = set(cache.get("seen_urls", []))

        for query in queries:
            try:
                # WebSearch 実行（MCP経由）
                results = self.web_search_func(query)

                for result in results:
                    url = result.get("url", "")
                    title = result.get("title", "")
                    snippet = result.get("snippet", "")

                    # 重複・除外チェック
                    if url in seen_urls:
                        continue
                    if self._is_excluded(f"{title} {snippet}"):
                        continue

                    seen_urls.add(url)

                    entry = CollectedEntry(
                        source_name="competitor_trends",
                        source_type=SourceType.WEB_SEARCH,
                        title=title,
                        url=url,
                        summary=snippet,
                        published_at=datetime.now(timezone.utc),
                        categories=[Category.OTHER],
                        keywords=[query],
                        raw_data={"query": query, "result": result},
                    )
                    entries.append(entry)

            except Exception as e:
                errors.append(f"検索エラー ({query}): {e}")

        # キャッシュ更新
        cache["seen_urls"] = list(seen_urls)[-500:]  # 最新500件のみ保持
        self._save_cache(cache)

        return CollectionResult(
            source_name="competitor_trends",
            source_type=SourceType.WEB_SEARCH,
            entries=entries,
            errors=errors,
        )

    def collect_competitors(self) -> CollectionResult:
        """
        競合キーワードで検索して収集

        Returns:
            CollectionResult: 収集結果
        """
        entries = []
        errors = []

        if not self.web_search_func:
            return CollectionResult(
                source_name="competitor_analysis",
                source_type=SourceType.WEB_SEARCH,
                entries=[],
                errors=["WebSearch 関数が設定されていません"],
            )

        queries = self.config.get("search_queries", {}).get("competitors", [])
        cache = self._load_cache()
        seen_urls = set(cache.get("seen_urls", []))

        for query in queries:
            try:
                results = self.web_search_func(query)

                for result in results:
                    url = result.get("url", "")
                    title = result.get("title", "")
                    snippet = result.get("snippet", "")

                    if url in seen_urls:
                        continue
                    if self._is_excluded(f"{title} {snippet}"):
                        continue

                    seen_urls.add(url)

                    entry = CollectedEntry(
                        source_name="competitor_analysis",
                        source_type=SourceType.WEB_SEARCH,
                        title=title,
                        url=url,
                        summary=snippet,
                        published_at=datetime.now(timezone.utc),
                        categories=[Category.OTHER],
                        keywords=[query],
                        raw_data={"query": query, "result": result},
                    )
                    entries.append(entry)

            except Exception as e:
                errors.append(f"検索エラー ({query}): {e}")

        cache["seen_urls"] = list(seen_urls)[-500:]
        self._save_cache(cache)

        return CollectionResult(
            source_name="competitor_analysis",
            source_type=SourceType.WEB_SEARCH,
            entries=entries,
            errors=errors,
        )

    def collect_opportunities(self) -> CollectionResult:
        """
        ビジネス機会キーワードで検索

        Returns:
            CollectionResult: 収集結果
        """
        entries = []
        errors = []

        if not self.web_search_func:
            return CollectionResult(
                source_name="opportunities",
                source_type=SourceType.WEB_SEARCH,
                entries=[],
                errors=["WebSearch 関数が設定されていません"],
            )

        queries = self.config.get("search_queries", {}).get("opportunities", [])
        cache = self._load_cache()
        seen_urls = set(cache.get("seen_urls", []))

        for query in queries:
            try:
                results = self.web_search_func(query)

                for result in results:
                    url = result.get("url", "")
                    title = result.get("title", "")
                    snippet = result.get("snippet", "")

                    if url in seen_urls:
                        continue
                    if self._is_excluded(f"{title} {snippet}"):
                        continue

                    seen_urls.add(url)

                    entry = CollectedEntry(
                        source_name="opportunities",
                        source_type=SourceType.WEB_SEARCH,
                        title=title,
                        url=url,
                        summary=snippet,
                        published_at=datetime.now(timezone.utc),
                        categories=[Category.OTHER],
                        keywords=[query],
                        raw_data={"query": query, "result": result},
                    )
                    entries.append(entry)

            except Exception as e:
                errors.append(f"検索エラー ({query}): {e}")

        cache["seen_urls"] = list(seen_urls)[-500:]
        self._save_cache(cache)

        return CollectionResult(
            source_name="opportunities",
            source_type=SourceType.WEB_SEARCH,
            entries=entries,
            errors=errors,
        )

    def collect_crypto(self) -> CollectionResult:
        """
        仮想通貨 × AI キーワードで検索

        Returns:
            CollectionResult: 収集結果
        """
        entries = []
        errors = []

        if not self.web_search_func:
            return CollectionResult(
                source_name="crypto_ai",
                source_type=SourceType.WEB_SEARCH,
                entries=[],
                errors=["WebSearch 関数が設定されていません"],
            )

        # crypto_ai, crypto_trends, crypto_opportunities を統合
        crypto_categories = ["crypto_ai", "crypto_trends", "crypto_opportunities"]
        all_queries = []
        for cat in crypto_categories:
            all_queries.extend(
                self.config.get("search_queries", {}).get(cat, [])
            )

        cache = self._load_cache()
        seen_urls = set(cache.get("seen_urls", []))

        for query in all_queries:
            try:
                results = self.web_search_func(query)

                for result in results:
                    url = result.get("url", "")
                    title = result.get("title", "")
                    snippet = result.get("snippet", "")

                    if url in seen_urls:
                        continue
                    if self._is_excluded(f"{title} {snippet}"):
                        continue

                    seen_urls.add(url)

                    entry = CollectedEntry(
                        source_name="crypto_ai",
                        source_type=SourceType.WEB_SEARCH,
                        title=title,
                        url=url,
                        summary=snippet,
                        published_at=datetime.now(timezone.utc),
                        categories=[Category.OTHER],
                        keywords=[query],
                        raw_data={"query": query, "result": result},
                    )
                    entries.append(entry)

            except Exception as e:
                errors.append(f"検索エラー ({query}): {e}")

        cache["seen_urls"] = list(seen_urls)[-500:]
        self._save_cache(cache)

        return CollectionResult(
            source_name="crypto_ai",
            source_type=SourceType.WEB_SEARCH,
            entries=entries,
            errors=errors,
        )

    def collect_all(self) -> list[CollectionResult]:
        """
        全カテゴリを収集

        Returns:
            list[CollectionResult]: 全収集結果
        """
        return [
            self.collect_trends(),
            self.collect_competitors(),
            self.collect_opportunities(),
            self.collect_crypto(),
        ]

    def save_results(self, results: list[CollectionResult]) -> Path:
        """
        収集結果を JSON で保存

        Args:
            results: 収集結果リスト

        Returns:
            Path: 保存先パス
        """
        now = datetime.now(timezone.utc)
        filename = f"competitor-{now.strftime('%Y-%m-%d')}.json"
        output_path = self.output_dir / filename

        data = {
            "collected_at": now.isoformat(),
            "results": [],
        }

        for result in results:
            result_data = {
                "source_name": result.source_name,
                "entries_count": len(result.entries),
                "errors": result.errors,
                "entries": [
                    {
                        "title": e.title,
                        "url": e.url,
                        "summary": e.summary,
                        "keywords": e.keywords,
                        "published_at": e.published_at.isoformat()
                        if e.published_at
                        else None,
                    }
                    for e in result.entries
                ],
            }
            data["results"].append(result_data)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path
