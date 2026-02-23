"""ニュースサイト横断収集。"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from collectors.models import CollectionResult, SourceType
from collectors.rss_collector import RSSCollector
from collectors.tag_filter import matches_include_tags


class NewsCrosscheckCollector:
    """news_sites.yaml で定義されたニュースサイトを収集する。"""

    def __init__(
        self,
        sources_dir: Path,
        cache_dir: Path,
        keywords_path: Optional[Path] = None,
    ):
        self.sources_dir = sources_dir
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rss_collector = RSSCollector(
            sources_dir=sources_dir,
            cache_dir=cache_dir,
            keywords_path=keywords_path,
        )
        self.config = self._load_config()

    def _load_config(self, include_tags: list[str] | None = None) -> dict:
        """news_sites.yaml を読み込み、必要なら tags で絞り込む。"""
        config_path = self.sources_dir / "news_sites.yaml"
        if not config_path.exists():
            return {}

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        sites = config.get("sites", [])
        if include_tags is not None:
            sites = [s for s in sites if matches_include_tags(s.get("tags", []), include_tags)]
        config["sites"] = sites
        return config

    def collect(
        self,
        since: Optional[datetime] = None,
        include_tags: list[str] | None = None,
    ) -> CollectionResult:
        """定義済みニュースサイトを収集する。"""
        config = self._load_config(include_tags=include_tags)
        sites = config.get("sites", [])

        result = CollectionResult(
            source_name="news_crosscheck",
            source_type=SourceType.RSS,
            collected_at=datetime.now(timezone.utc),
        )

        if not sites:
            return result

        for site in sites:
            source_name = site.get("name", "")
            feed_url = site.get("rss") or site.get("url")
            tags = site.get("tags", [])
            if not source_name or not feed_url:
                continue

            feed_result = self.rss_collector.collect_feed(
                source_name=source_name,
                feed_url=feed_url,
                since=since,
            )
            if not feed_result.success:
                for err in feed_result.errors:
                    result.errors.append(f"[{source_name}] {err}")
                continue

            for entry in feed_result.entries:
                for tag in tags:
                    if tag not in entry.keywords:
                        entry.keywords.append(tag)
                result.entries.append(entry)

        result.success = not bool(result.errors)
        return result
