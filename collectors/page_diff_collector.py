"""
ページ差分検出
価格ページ・ドキュメントページなどの変更を監視
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import yaml

from collectors.models import Category, CollectedEntry, CollectionResult, SourceType


class PageDiffCollector:
    """ページの差分を検出"""

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

        # HTTP クライアント
        self.client = httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AIUpdateRadar/1.0)"
            },
        )

    def _load_keywords(self, keywords_path: Optional[Path]) -> dict:
        """keywords.yaml を読み込み"""
        if keywords_path and keywords_path.exists():
            with open(keywords_path) as f:
                return yaml.safe_load(f) or {}
        return {}

    def _get_cache_path(self, page_id: str) -> Path:
        """キャッシュファイルのパスを取得"""
        # ファイル名に使える形式に変換
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", page_id)
        return self.cache_dir / f"{safe_id}_page_cache.json"

    def _load_cache(self, page_id: str) -> dict:
        """キャッシュを読み込み"""
        cache_path = self._get_cache_path(page_id)
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return {}

    def _save_cache(self, page_id: str, content_hash: str, content: str) -> None:
        """キャッシュを保存"""
        cache_path = self._get_cache_path(page_id)
        with open(cache_path, "w") as f:
            json.dump(
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "content_hash": content_hash,
                    "content_preview": content[:1000],  # プレビュー用
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

    def _extract_text(self, html: str) -> str:
        """HTML からテキストを抽出（簡易版）"""
        # スクリプト・スタイルを除去
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        # タグを除去
        text = re.sub(r"<[^>]+>", " ", html)
        # 空白を正規化
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _compute_hash(self, content: str) -> str:
        """コンテンツのハッシュを計算"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _classify_change(
        self, text: str, page_type: str, provider_keywords: dict
    ) -> tuple[list[Category], list[str]]:
        """変更をカテゴリ分類"""
        categories = []
        matched_keywords = []
        text_lower = text.lower()

        # ページタイプに基づく分類
        if page_type == "pricing":
            categories.append(Category.PRICING)
        elif page_type in ("docs", "changelog"):
            categories.append(Category.CAPABILITY)

        # プロバイダー固有のキーワードチェック
        for cat_key, kw_list in provider_keywords.items():
            if isinstance(kw_list, list):
                for kw in kw_list:
                    if kw.lower() in text_lower:
                        matched_keywords.append(kw)
                        if cat_key == "capability":
                            if Category.CAPABILITY not in categories:
                                categories.append(Category.CAPABILITY)
                        elif cat_key == "constraint":
                            if Category.CONSTRAINT not in categories:
                                categories.append(Category.CONSTRAINT)
                        elif cat_key == "pricing":
                            if Category.PRICING not in categories:
                                categories.append(Category.PRICING)

        return categories if categories else [Category.OTHER], matched_keywords

    def check_page(
        self,
        page_id: str,
        url: str,
        page_type: str = "other",
        provider_keywords: dict = None,
    ) -> CollectionResult:
        """ページの変更をチェック"""
        provider_keywords = provider_keywords or {}

        result = CollectionResult(
            source_name=page_id,
            source_type=SourceType.PAGE_DIFF,
            collected_at=datetime.now(timezone.utc),
        )

        try:
            # ページ取得
            response = self.client.get(url)
            response.raise_for_status()

            # テキスト抽出
            text = self._extract_text(response.text)
            content_hash = self._compute_hash(text)

            # キャッシュと比較
            cache = self._load_cache(page_id)
            old_hash = cache.get("content_hash", "")

            if old_hash and old_hash != content_hash:
                # 変更あり
                categories, keywords = self._classify_change(text, page_type, provider_keywords)

                collected = CollectedEntry(
                    title=f"[{page_id}] ページ更新を検出",
                    url=url,
                    source_name=page_id,
                    source_type=SourceType.PAGE_DIFF,
                    published_at=datetime.now(timezone.utc),
                    summary=f"ハッシュ変更: {old_hash} → {content_hash}",
                    categories=categories,
                    keywords=keywords,
                    raw_content=text[:2000],  # 変更後のコンテンツ（一部）
                )
                result.entries.append(collected)

            # キャッシュ更新
            self._save_cache(page_id, content_hash, text)

        except httpx.HTTPError as e:
            result.errors.append(f"HTTP error: {e}")
            result.success = False
        except Exception as e:
            result.errors.append(f"Unexpected error: {e}")
            result.success = False

        return result

    def collect_all(self) -> list[CollectionResult]:
        """providers.yaml の全ページを監視"""
        results = []

        providers_path = self.sources_dir / "providers.yaml"
        if not providers_path.exists():
            return results

        with open(providers_path) as f:
            config = yaml.safe_load(f) or {}

        for provider_id, provider_data in config.get("providers", {}).items():
            provider_keywords = provider_data.get("keywords", {})

            for source in provider_data.get("sources", []):
                source_type = source.get("type", "other")
                url = source.get("url")

                if not url:
                    continue

                # RSS があるソースはスキップ（RSS Collector が担当）
                if source.get("rss"):
                    continue

                page_id = f"{provider_id}-{source_type}"

                result = self.check_page(
                    page_id=page_id,
                    url=url,
                    page_type=source_type,
                    provider_keywords=provider_keywords,
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

    from rich.console import Console
    from rich.table import Table

    parser = argparse.ArgumentParser(description="ページ差分検出")
    parser.add_argument("--url", help="特定の URL のみチェック")
    parser.add_argument("--id", help="ページ ID（--url と併用）")
    parser.add_argument("--json", action="store_true", help="JSON 出力")
    parser.add_argument("--force-init", action="store_true", help="キャッシュを初期化")
    args = parser.parse_args()

    console = Console()

    # パス設定
    base_dir = Path(__file__).parent.parent
    sources_dir = base_dir / "sources"
    cache_dir = base_dir / ".private" / "cache"
    keywords_path = sources_dir / "keywords.yaml"

    # キャッシュ初期化
    if args.force_init:
        if cache_dir.exists():
            for f in cache_dir.glob("*_page_cache.json"):
                f.unlink()
            console.print("[yellow]キャッシュを初期化しました[/yellow]")

    collector = PageDiffCollector(
        sources_dir=sources_dir,
        cache_dir=cache_dir,
        keywords_path=keywords_path,
    )

    if args.url:
        page_id = args.id or args.url.split("/")[-1] or "page"
        result = collector.check_page(page_id=page_id, url=args.url)
        results = [result]
    else:
        results = collector.collect_all()

    # 出力
    if args.json:
        output = [r.to_dict() for r in results]
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        changes_found = False
        for result in results:
            if result.entries:
                changes_found = True
                table = Table(title=f"{result.source_name} - 変更検出")
                table.add_column("URL")
                table.add_column("Category")
                table.add_column("Keywords", style="cyan")

                for entry in result.entries:
                    cats = ", ".join(c.value for c in entry.categories)
                    kws = ", ".join(entry.keywords[:5])
                    table.add_row(entry.url[:60], cats, kws)

                console.print(table)
                console.print()

            if result.errors:
                for err in result.errors:
                    console.print(f"[red]Error ({result.source_name}): {err}[/red]")

        if not changes_found:
            console.print("[dim]変更は検出されませんでした（または初回実行）[/dim]")


if __name__ == "__main__":
    main()
