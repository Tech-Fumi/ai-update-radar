"""
GitHub リリース収集
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import yaml

from collectors.models import Category, CollectedEntry, CollectionResult, SourceType


class GitHubCollector:
    """GitHub リリースを収集"""

    GITHUB_API_BASE = "https://api.github.com"

    def __init__(
        self,
        sources_dir: Path,
        cache_dir: Path,
        token: Optional[str] = None,
        keywords_path: Optional[Path] = None,
    ):
        self.sources_dir = sources_dir
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.token = token

        # HTTP クライアント設定
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self.client = httpx.Client(headers=headers, timeout=30)

        # キーワード読み込み
        self.keywords = self._load_keywords(keywords_path)

    def _load_keywords(self, keywords_path: Optional[Path]) -> dict:
        """keywords.yaml を読み込み"""
        if keywords_path and keywords_path.exists():
            with open(keywords_path) as f:
                return yaml.safe_load(f) or {}
        return {}

    def _get_cache_path(self, repo_id: str) -> Path:
        """キャッシュファイルのパスを取得"""
        return self.cache_dir / f"{repo_id}_github_cache.json"

    def _load_cache(self, repo_id: str) -> set[str]:
        """キャッシュされたリリースタグを読み込み"""
        cache_path = self._get_cache_path(repo_id)
        if cache_path.exists():
            with open(cache_path) as f:
                data = json.load(f)
                return set(data.get("seen_tags", []))
        return set()

    def _save_cache(self, repo_id: str, seen_tags: set[str]) -> None:
        """キャッシュを保存"""
        cache_path = self._get_cache_path(repo_id)
        with open(cache_path, "w") as f:
            json.dump(
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "seen_tags": list(seen_tags),
                },
                f,
                indent=2,
            )

    def _classify_release(
        self, title: str, body: str, repo_keywords: list[str]
    ) -> tuple[list[Category], list[str]]:
        """リリースをカテゴリ分類"""
        categories = []
        matched_keywords = []
        text = f"{title} {body}".lower()

        # リポジトリ固有のキーワードをチェック
        for kw in repo_keywords:
            if kw.lower() in text:
                matched_keywords.append(kw)

        # グローバルキーワードでカテゴリ分類
        if self.keywords.get("categories"):
            for cat_name, cat_data in self.keywords["categories"].items():
                if cat_name == "other":
                    continue

                for sub_keywords in cat_data.values():
                    if isinstance(sub_keywords, list):
                        for kw in sub_keywords:
                            if kw.lower() in text:
                                if kw not in matched_keywords:
                                    matched_keywords.append(kw)
                                cat = (
                                    Category(cat_name)
                                    if cat_name in Category._value2member_map_
                                    else Category.OTHER
                                )
                                if cat not in categories:
                                    categories.append(cat)

        # BREAKING CHANGE は特に重要
        if "breaking" in text:
            if Category.CAPABILITY not in categories:
                categories.append(Category.CAPABILITY)
            if "breaking" not in [k.lower() for k in matched_keywords]:
                matched_keywords.append("BREAKING")

        return categories if categories else [Category.OTHER], matched_keywords

    def collect_releases(
        self,
        repo_id: str,
        repo_path: str,
        repo_keywords: list[str] = None,
        since: Optional[datetime] = None,
        limit: int = 10,
    ) -> CollectionResult:
        """単一リポジトリのリリースを収集"""
        repo_keywords = repo_keywords or []

        result = CollectionResult(
            source_name=repo_id,
            source_type=SourceType.GITHUB_RELEASE,
            collected_at=datetime.now(timezone.utc),
        )

        try:
            # リリース取得
            url = f"{self.GITHUB_API_BASE}/repos/{repo_path}/releases"
            response = self.client.get(url, params={"per_page": limit})
            response.raise_for_status()

            releases = response.json()

            # キャッシュ読み込み
            seen_tags = self._load_cache(repo_id)

            for release in releases:
                tag = release.get("tag_name", "")

                # 既に見たリリースはスキップ
                if tag in seen_tags:
                    continue

                # 日付パース
                published_at = None
                if release.get("published_at"):
                    published_at = datetime.fromisoformat(
                        release["published_at"].replace("Z", "+00:00")
                    )

                # since フィルタ
                if since and published_at and published_at < since:
                    continue

                # カテゴリ分類
                title = release.get("name") or tag
                body = release.get("body") or ""
                categories, keywords = self._classify_release(title, body, repo_keywords)

                # サマリ作成（最初の500文字）
                summary = body[:500] if body else ""

                collected = CollectedEntry(
                    title=f"[{repo_path}] {title}",
                    url=release.get("html_url", ""),
                    source_name=repo_id,
                    source_type=SourceType.GITHUB_RELEASE,
                    published_at=published_at,
                    summary=summary,
                    categories=categories,
                    keywords=keywords,
                    raw_content=body,
                )
                result.entries.append(collected)
                seen_tags.add(tag)

            # キャッシュ保存
            self._save_cache(repo_id, seen_tags)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                result.errors.append(f"Repository not found: {repo_path}")
            elif e.response.status_code == 403:
                result.errors.append("Rate limit exceeded or authentication required")
            else:
                result.errors.append(f"HTTP error {e.response.status_code}: {e}")
            result.success = False
        except Exception as e:
            result.errors.append(f"Unexpected error: {e}")
            result.success = False

        return result

    def collect_all(self, since: Optional[datetime] = None) -> list[CollectionResult]:
        """repositories.yaml の全リポジトリを収集"""
        results = []

        repos_path = self.sources_dir / "repositories.yaml"
        if not repos_path.exists():
            return results

        with open(repos_path) as f:
            config = yaml.safe_load(f) or {}

        for repo_id, repo_data in config.get("repositories", {}).items():
            repo_path = repo_data.get("repo")
            if not repo_path:
                continue

            # releases を監視対象にしているリポジトリのみ
            watch = repo_data.get("watch", [])
            if "releases" not in watch:
                continue

            keywords = repo_data.get("keywords", [])

            result = self.collect_releases(
                repo_id=repo_id,
                repo_path=repo_path,
                repo_keywords=keywords,
                since=since,
            )
            results.append(result)

        return results

    def __del__(self):
        """クリーンアップ"""
        if hasattr(self, "client"):
            self.client.close()


def main():
    """CLI エントリポイント"""
    import argparse
    import os

    from rich.console import Console
    from rich.table import Table

    parser = argparse.ArgumentParser(description="GitHub リリース収集")
    parser.add_argument("--repo", help="特定のリポジトリのみ収集（例: openai/openai-python）")
    parser.add_argument("--days", type=int, default=7, help="過去N日分を収集")
    parser.add_argument("--json", action="store_true", help="JSON 出力")
    args = parser.parse_args()

    console = Console()

    # パス設定
    base_dir = Path(__file__).parent.parent
    sources_dir = base_dir / "sources"
    cache_dir = base_dir / ".private" / "cache"
    keywords_path = sources_dir / "keywords.yaml"

    # トークン取得（環境変数から）
    token = os.environ.get("GITHUB_TOKEN")

    collector = GitHubCollector(
        sources_dir=sources_dir,
        cache_dir=cache_dir,
        token=token,
        keywords_path=keywords_path,
    )

    # 収集
    from datetime import timedelta

    since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    since = since - timedelta(days=args.days)

    if args.repo:
        # 単一リポジトリ
        result = collector.collect_releases(
            repo_id=args.repo.replace("/", "_"),
            repo_path=args.repo,
            since=since,
        )
        results = [result]
    else:
        results = collector.collect_all(since=since)

    # 出力
    if args.json:
        output = [r.to_dict() for r in results]
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        for result in results:
            if result.entries:
                table = Table(title=f"{result.source_name} ({len(result.entries)} releases)")
                table.add_column("Date", style="dim")
                table.add_column("Title")
                table.add_column("Category")
                table.add_column("Keywords", style="cyan")

                for entry in result.entries[:10]:
                    date_str = entry.published_at.strftime("%m/%d") if entry.published_at else "-"
                    cats = ", ".join(c.value for c in entry.categories)
                    kws = ", ".join(entry.keywords[:3])
                    table.add_row(date_str, entry.title[:60], cats, kws)

                console.print(table)
                console.print()

            if result.errors:
                for err in result.errors:
                    console.print(f"[red]Error: {err}[/red]")


if __name__ == "__main__":
    main()
