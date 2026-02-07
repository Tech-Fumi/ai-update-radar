"""
Zenn 記事収集（段階フィルター方式 ①）

RSSCollector をコンポジションで利用し、Zenn トピック別の記事を収集する。
soft filter でスコア付け + 除外理由を記録（ハードブロックしない）。
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import yaml

from collectors.models import CollectedEntry, CollectionResult, SourceType
from collectors.rss_collector import RSSCollector


# トラッキングパラメータ（除去対象）
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "source", "fbclid", "gclid", "mc_cid", "mc_eid",
}


def normalize_url(url: str) -> str:
    """URL を正規化（トラッキングパラメータのみ除去）"""
    parsed = urlparse(url)

    # hostname 小文字化
    netloc = parsed.netloc.lower()

    # トラッキングパラメータ除去
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {
            k: v for k, v in params.items()
            if k not in TRACKING_PARAMS and not k.startswith("utm_")
        }
        query = urlencode(filtered, doseq=True) if filtered else ""
    else:
        query = ""

    # 末尾スラッシュ正規化
    path = parsed.path.rstrip("/") if parsed.path != "/" else "/"

    # fragment 除去、再構築
    return urlunparse((parsed.scheme, netloc, path, parsed.params, query, ""))


class ZennCollector:
    """Zenn 記事を収集（RSSCollector をコンポジションで利用）"""

    def __init__(
        self,
        sources_dir: Path,
        cache_dir: Path,
        keywords_path: Optional[Path] = None,
    ):
        self.sources_dir = sources_dir
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # RSSCollector をコンポジションで利用
        self.rss_collector = RSSCollector(
            sources_dir=sources_dir,
            cache_dir=cache_dir,
            keywords_path=keywords_path,
        )

        # articles.yaml 読み込み
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """articles.yaml を読み込み"""
        config_path = self.sources_dir / "articles.yaml"
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        return {}

    def _get_zenn_config(self) -> dict:
        """Zenn のフィード設定を取得"""
        return self.config.get("feeds", {}).get("zenn", {})

    def _get_prefilter_config(self) -> dict:
        """prefilter 設定を取得"""
        return self._get_zenn_config().get("prefilter", {})

    def _calculate_score(self, title: str, summary: str) -> tuple[int, list[str], list[str]]:
        """soft filter スコアを計算

        Returns:
            (score, boost_matched, penalize_matched)
        """
        prefilter = self._get_prefilter_config()
        boost_keywords = prefilter.get("boost_keywords", [])
        penalize_keywords = prefilter.get("penalize_keywords", [])

        text = f"{title} {summary}".lower()
        score = 0
        boost_matched = []
        penalize_matched = []

        for kw in boost_keywords:
            if kw.lower() in text:
                score += 1
                boost_matched.append(kw)

        for kw in penalize_keywords:
            if kw.lower() in text:
                score -= 1
                penalize_matched.append(kw)

        return score, boost_matched, penalize_matched

    def _get_dedup_key(self, entry_id: str, url: str) -> str:
        """重複検知キーを取得（entry_id 優先 → 正規化 URL）"""
        if entry_id:
            return f"id:{entry_id}"
        return f"url:{normalize_url(url)}"

    def _load_seen_keys(self) -> set[str]:
        """既に収集済みのキーを読み込み"""
        cache_path = self.cache_dir / "zenn_seen_keys.json"
        if cache_path.exists():
            with open(cache_path) as f:
                data = json.load(f)
                return set(data.get("seen_keys", []))
        return set()

    def _save_seen_keys(self, seen_keys: set[str]) -> None:
        """収集済みキーを保存"""
        cache_path = self.cache_dir / "zenn_seen_keys.json"
        with open(cache_path, "w") as f:
            json.dump(
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "seen_keys": list(seen_keys),
                },
                f,
                indent=2,
            )

    def collect(
        self,
        since: Optional[datetime] = None,
        min_score: Optional[int] = None,
    ) -> CollectionResult:
        """Zenn の全トピックから記事を収集

        Args:
            since: この日時以降の記事のみ収集
            min_score: この値以上のスコアのエントリのみ含める（None で設定値を使用）
        """
        zenn_config = self._get_zenn_config()
        prefilter = self._get_prefilter_config()

        if min_score is None:
            min_score = prefilter.get("default_min_score", -1)

        result = CollectionResult(
            source_name="zenn",
            source_type=SourceType.RSS,
            collected_at=datetime.now(timezone.utc),
        )

        feeds = zenn_config.get("feeds", [])
        if not feeds:
            result.errors.append("articles.yaml に Zenn フィード定義がありません")
            result.success = False
            return result

        # 重複検知キー読み込み
        seen_keys = self._load_seen_keys()
        initial_count = len(seen_keys)

        for feed_def in feeds:
            slug = feed_def.get("slug", "")
            url = feed_def.get("url", "")
            tags = feed_def.get("tags", [])

            if not url:
                continue

            # RSSCollector で収集
            feed_result = self.rss_collector.collect_feed(
                source_name=f"zenn-{slug}",
                feed_url=url,
                since=since,
            )

            if not feed_result.success:
                for err in feed_result.errors:
                    result.errors.append(f"[{slug}] {err}")
                # エラーがあっても他のフィードは処理続行
                continue

            for entry in feed_result.entries:
                # 重複検知
                entry_id = ""
                if entry.raw_data and entry.raw_data.get("id"):
                    entry_id = entry.raw_data["id"]

                dedup_key = self._get_dedup_key(entry_id, entry.url)
                if dedup_key in seen_keys:
                    continue

                # soft filter スコア計算
                score, boost_matched, penalize_matched = self._calculate_score(
                    entry.title, entry.summary
                )

                # フィルタ結果を raw_content に記録
                filter_result = {
                    "prefilter_score": score,
                    "boost_matched": boost_matched,
                    "penalize_matched": penalize_matched,
                    "source_topic": slug,
                    "source_tags": tags,
                }
                entry.raw_content = json.dumps(filter_result, ensure_ascii=False)

                # ソース名を統一
                entry.source_name = "zenn"

                # タグをキーワードに追加
                for tag in tags:
                    if tag not in entry.keywords:
                        entry.keywords.append(tag)

                # min_score フィルタ
                if score >= min_score:
                    result.entries.append(entry)

                seen_keys.add(dedup_key)

        # キャッシュ保存
        self._save_seen_keys(seen_keys)

        new_count = len(seen_keys) - initial_count
        if new_count > 0:
            result.success = True

        return result
