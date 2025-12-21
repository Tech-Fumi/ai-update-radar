"""
AI Update Radar - 統合 CLI
全コレクターを統合して実行
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from collectors.github_collector import GitHubCollector
from collectors.models import Category, CollectionResult
from collectors.page_diff_collector import PageDiffCollector
from collectors.rss_collector import RSSCollector

app = typer.Typer(help="AI Update Radar - AI アップデート監視ツール")
console = Console()


def get_paths() -> tuple[Path, Path, Path, Path]:
    """パス設定を取得"""
    base_dir = Path(__file__).parent.parent
    sources_dir = base_dir / "sources"
    cache_dir = base_dir / ".private" / "cache"
    keywords_path = sources_dir / "keywords.yaml"
    exports_dir = base_dir / "exports"
    return sources_dir, cache_dir, keywords_path, exports_dir


def format_results_table(results: list[CollectionResult], title: str) -> None:
    """結果をテーブル形式で表示"""
    all_entries = []
    for result in results:
        all_entries.extend(result.entries)

    if not all_entries:
        console.print(f"[dim]{title}: 新しいエントリなし[/dim]")
        return

    # 日付でソート
    all_entries.sort(key=lambda e: e.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    table = Table(title=f"{title} ({len(all_entries)} 件)")
    table.add_column("日付", style="dim", width=6)
    table.add_column("ソース", width=20)
    table.add_column("タイトル", width=50)
    table.add_column("カテゴリ", width=12)
    table.add_column("キーワード", style="cyan", width=20)

    for entry in all_entries[:20]:  # 最大20件
        date_str = entry.published_at.strftime("%m/%d") if entry.published_at else "-"
        cats = ", ".join(c.value for c in entry.categories[:2])
        kws = ", ".join(entry.keywords[:3])
        table.add_row(date_str, entry.source_name[:20], entry.title[:50], cats, kws)

    console.print(table)


def print_errors(results: list[CollectionResult]) -> None:
    """エラーを表示"""
    for result in results:
        for err in result.errors:
            console.print(f"[red]Error ({result.source_name}): {err}[/red]")


@app.command()
def collect(
    days: int = typer.Option(7, help="過去N日分を収集"),
    rss: bool = typer.Option(True, help="RSS を収集"),
    github: bool = typer.Option(True, help="GitHub リリースを収集"),
    pages: bool = typer.Option(True, help="ページ差分を検出"),
    export: bool = typer.Option(False, help="JSON にエクスポート"),
    output: Optional[str] = typer.Option(None, help="エクスポート先ファイル名"),
):
    """
    全ソースから情報を収集

    デフォルトで RSS、GitHub、ページ差分をすべて収集
    """
    sources_dir, cache_dir, keywords_path, exports_dir = get_paths()

    since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    since = since - timedelta(days=days)

    all_results: list[CollectionResult] = []

    # RSS 収集
    if rss:
        console.print("[bold]📰 RSS フィード収集中...[/bold]")
        rss_collector = RSSCollector(
            sources_dir=sources_dir,
            cache_dir=cache_dir,
            keywords_path=keywords_path,
        )
        rss_results = rss_collector.collect_all(since=since)
        all_results.extend(rss_results)
        format_results_table(rss_results, "RSS フィード")
        print_errors(rss_results)
        console.print()

    # GitHub 収集
    if github:
        console.print("[bold]🐙 GitHub リリース収集中...[/bold]")
        github_collector = GitHubCollector(
            sources_dir=sources_dir,
            cache_dir=cache_dir,
            token=os.environ.get("GITHUB_TOKEN"),
            keywords_path=keywords_path,
        )
        github_results = github_collector.collect_all(since=since)
        all_results.extend(github_results)
        format_results_table(github_results, "GitHub リリース")
        print_errors(github_results)
        console.print()

    # ページ差分
    if pages:
        console.print("[bold]🔍 ページ差分検出中...[/bold]")
        page_collector = PageDiffCollector(
            sources_dir=sources_dir,
            cache_dir=cache_dir,
            keywords_path=keywords_path,
        )
        page_results = page_collector.collect_all()
        all_results.extend(page_results)
        format_results_table(page_results, "ページ差分")
        print_errors(page_results)
        console.print()

    # サマリ
    total_entries = sum(len(r.entries) for r in all_results)
    total_errors = sum(len(r.errors) for r in all_results)

    summary = Panel(
        f"📊 収集完了\n"
        f"  • エントリ: {total_entries} 件\n"
        f"  • エラー: {total_errors} 件\n"
        f"  • 期間: 過去 {days} 日",
        title="サマリ",
        border_style="green" if total_errors == 0 else "yellow",
    )
    console.print(summary)

    # エクスポート
    if export:
        exports_dir.mkdir(parents=True, exist_ok=True)
        if output:
            export_path = exports_dir / output
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = exports_dir / f"collection_{timestamp}.json"

        export_data = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "days": days,
            "results": [r.to_dict() for r in all_results],
        }

        with open(export_path, "w") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        console.print(f"[green]✅ エクスポート完了: {export_path}[/green]")


@app.command()
def summary(
    days: int = typer.Option(7, help="過去N日分を集計"),
    category: Optional[str] = typer.Option(None, help="カテゴリでフィルタ"),
):
    """
    収集結果のサマリを表示

    カテゴリ別・ソース別の集計
    """
    sources_dir, cache_dir, keywords_path, exports_dir = get_paths()

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # 全コレクター実行
    all_entries = []

    # RSS
    rss_collector = RSSCollector(sources_dir=sources_dir, cache_dir=cache_dir, keywords_path=keywords_path)
    for result in rss_collector.collect_all(since=since):
        all_entries.extend(result.entries)

    # GitHub
    github_collector = GitHubCollector(
        sources_dir=sources_dir,
        cache_dir=cache_dir,
        token=os.environ.get("GITHUB_TOKEN"),
        keywords_path=keywords_path,
    )
    for result in github_collector.collect_all(since=since):
        all_entries.extend(result.entries)

    # カテゴリフィルタ
    if category:
        try:
            cat_filter = Category(category)
            all_entries = [e for e in all_entries if cat_filter in e.categories]
        except ValueError:
            console.print(f"[red]不正なカテゴリ: {category}[/red]")
            console.print(f"有効なカテゴリ: {[c.value for c in Category]}")
            return

    # カテゴリ別集計
    cat_counts = {}
    for entry in all_entries:
        for cat in entry.categories:
            cat_counts[cat.value] = cat_counts.get(cat.value, 0) + 1

    # ソース別集計
    source_counts = {}
    for entry in all_entries:
        source_counts[entry.source_name] = source_counts.get(entry.source_name, 0) + 1

    # 表示
    console.print(Panel(f"過去 {days} 日間のサマリ", style="bold"))

    if cat_counts:
        cat_table = Table(title="カテゴリ別")
        cat_table.add_column("カテゴリ")
        cat_table.add_column("件数", justify="right")
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            cat_table.add_row(cat, str(count))
        console.print(cat_table)
    else:
        console.print("[dim]エントリなし[/dim]")

    if source_counts:
        source_table = Table(title="ソース別")
        source_table.add_column("ソース")
        source_table.add_column("件数", justify="right")
        for source, count in sorted(source_counts.items(), key=lambda x: -x[1])[:10]:
            source_table.add_row(source, str(count))
        console.print(source_table)


@app.command()
def sources():
    """監視対象ソースの一覧を表示"""
    sources_dir, _, _, _ = get_paths()

    # プロバイダー
    providers_path = sources_dir / "providers.yaml"
    if providers_path.exists():
        with open(providers_path) as f:
            providers = yaml.safe_load(f) or {}

        table = Table(title="📰 プロバイダー")
        table.add_column("ID")
        table.add_column("名前")
        table.add_column("優先度")
        table.add_column("ソース数")

        for pid, pdata in providers.get("providers", {}).items():
            table.add_row(
                pid,
                pdata.get("name", ""),
                str(pdata.get("priority", "-")),
                str(len(pdata.get("sources", []))),
            )
        console.print(table)
        console.print()

    # リポジトリ
    repos_path = sources_dir / "repositories.yaml"
    if repos_path.exists():
        with open(repos_path) as f:
            repos = yaml.safe_load(f) or {}

        table = Table(title="🐙 GitHub リポジトリ")
        table.add_column("ID")
        table.add_column("リポジトリ")
        table.add_column("優先度")
        table.add_column("監視対象")

        for rid, rdata in repos.get("repositories", {}).items():
            table.add_row(
                rid,
                rdata.get("repo", ""),
                str(rdata.get("priority", "-")),
                ", ".join(rdata.get("watch", [])),
            )
        console.print(table)


@app.command()
def init():
    """キャッシュを初期化（初回実行時に推奨）"""
    _, cache_dir, _, _ = get_paths()

    cache_dir.mkdir(parents=True, exist_ok=True)

    # 既存キャッシュを削除
    count = 0
    for f in cache_dir.glob("*.json"):
        f.unlink()
        count += 1

    if count > 0:
        console.print(f"[yellow]キャッシュを削除しました: {count} ファイル[/yellow]")
    else:
        console.print("[dim]キャッシュはありませんでした[/dim]")

    console.print("[green]✅ 初期化完了。次回 collect 時に全エントリが検出されます。[/green]")


if __name__ == "__main__":
    app()
