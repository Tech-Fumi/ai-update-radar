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
    min_dt = datetime.min.replace(tzinfo=timezone.utc)
    all_entries.sort(key=lambda e: e.published_at or min_dt, reverse=True)

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
    rss_collector = RSSCollector(
        sources_dir=sources_dir, cache_dir=cache_dir, keywords_path=keywords_path
    )
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


@app.command()
def evaluate(
    days: int = typer.Option(7, help="過去N日分を評価"),
    layer: Optional[int] = typer.Option(None, help="レイヤーでフィルタ (1=無視, 2=検知, 3=深掘り)"),
    log: bool = typer.Option(True, help="判断ログを保存"),
    report: bool = typer.Option(False, help="サマリレポートを表示"),
):
    """
    収集データを評価し、Layer 判定を行う

    スコアリング要素: 適用可能性、コスト削減、リスク、緊急性
    """
    from evaluators import EvaluationLogger, Layer, RelevanceScorer

    sources_dir, cache_dir, keywords_path, exports_dir = get_paths()

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # 全ソースからエントリを収集
    all_entries = []

    console.print("[bold]📊 データ収集中...[/bold]")

    # RSS
    rss_collector = RSSCollector(
        sources_dir=sources_dir, cache_dir=cache_dir, keywords_path=keywords_path
    )
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

    if not all_entries:
        console.print("[dim]評価対象のエントリがありません[/dim]")
        return

    console.print(f"[bold]🔍 {len(all_entries)} 件を評価中...[/bold]")

    # 評価
    scorer = RelevanceScorer()
    results = scorer.evaluate_batch(all_entries)

    # レイヤーフィルタ
    if layer:
        try:
            layer_filter = Layer(layer)
            results = [r for r in results if r.layer == layer_filter]
        except ValueError:
            console.print(f"[red]不正なレイヤー: {layer}[/red]")
            console.print("有効なレイヤー: 1=無視, 2=検知, 3=深掘り")
            return

    # 結果表示
    table = Table(title=f"評価結果 ({len(results)} 件)")
    table.add_column("Layer", width=8)
    table.add_column("Score", width=6)
    table.add_column("Cat", width=10)
    table.add_column("タイトル", width=40)
    table.add_column("理由", width=30)

    # レイヤー別にソート（高い方が上）
    results.sort(key=lambda r: (r.layer.value, r.relevance_score), reverse=True)

    layer_styles = {
        Layer.EXPERIMENT: "bold green",
        Layer.DETECT: "yellow",
        Layer.IGNORE: "dim",
    }

    for result in results[:30]:  # 最大30件
        style = layer_styles.get(result.layer, "")
        table.add_row(
            result.layer.name,
            f"{result.relevance_score:.1f}",
            result.classification.primary_category.value,
            result.entry.title[:40],
            result.reason[:30],
            style=style,
        )

    console.print(table)

    # 集計サマリ
    by_layer = {Layer.EXPERIMENT: 0, Layer.DETECT: 0, Layer.IGNORE: 0}
    for r in results:
        by_layer[r.layer] += 1

    summary_panel = Panel(
        f"🎯 深掘り対象: [bold green]{by_layer[Layer.EXPERIMENT]}[/bold green] 件\n"
        f"📋 検知のみ: [yellow]{by_layer[Layer.DETECT]}[/yellow] 件\n"
        f"🔇 無視: [dim]{by_layer[Layer.IGNORE]}[/dim] 件",
        title="評価サマリ",
        border_style="blue",
    )
    console.print(summary_panel)

    # ログ保存
    if log:
        logger = EvaluationLogger()
        log_path = logger.log_batch(results)
        console.print(f"[green]✅ 判断ログ保存: {log_path}[/green]")

    # サマリレポート
    if report:
        logger = EvaluationLogger()
        console.print()
        console.print(logger.generate_summary_report(days=days))


@app.command()
def export(
    days: int = typer.Option(7, help="過去N日分を評価・エクスポート"),
    digest: bool = typer.Option(True, help="週次ダイジェストを出力"),
    adopted: bool = typer.Option(True, help="採用決定リストを出力"),
    alerts: bool = typer.Option(True, help="技術アラートを出力"),
    notify: bool = typer.Option(False, help="infra-automation に通知"),
    ledger: bool = typer.Option(False, help="decision-ledger に記録"),
):
    """
    評価結果を他リポジトリ向けにエクスポート

    週次ダイジェスト（JSON）、採用決定リスト（YAML）、技術アラート（YAML）を出力
    """
    from evaluators import Exporter, Layer, RelevanceScorer

    sources_dir, cache_dir, keywords_path, exports_dir = get_paths()

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # 全ソースからエントリを収集
    all_entries = []

    console.print("[bold]📊 データ収集中...[/bold]")

    # RSS
    rss_collector = RSSCollector(
        sources_dir=sources_dir, cache_dir=cache_dir, keywords_path=keywords_path
    )
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

    if not all_entries:
        console.print("[dim]エクスポート対象のエントリがありません[/dim]")
        return

    console.print(f"[bold]🔍 {len(all_entries)} 件を評価中...[/bold]")

    # 評価
    scorer = RelevanceScorer()
    results = scorer.evaluate_batch(all_entries)

    # エクスポート
    exporter = Exporter()
    exported_paths = {}

    if digest:
        path = exporter.export_weekly_digest(results)
        exported_paths["digest"] = path
        console.print(f"[green]✅ 週次ダイジェスト: {path}[/green]")

    if adopted:
        path = exporter.export_adopted_list(results)
        exported_paths["adopted"] = path
        console.print(f"[green]✅ 採用決定リスト: {path}[/green]")

    if alerts:
        path = exporter.export_alerts(results)
        exported_paths["alerts"] = path
        console.print(f"[green]✅ 技術アラート: {path}[/green]")

    # サマリ
    layer_counts = {Layer.EXPERIMENT: 0, Layer.DETECT: 0, Layer.IGNORE: 0}
    for r in results:
        layer_counts[r.layer] += 1

    summary = Panel(
        f"📤 エクスポート完了\n"
        f"  • 評価: {len(results)} 件\n"
        f"  • 深掘り対象: {layer_counts[Layer.EXPERIMENT]} 件\n"
        f"  • 検知のみ: {layer_counts[Layer.DETECT]} 件\n"
        f"  • 出力ファイル: {len(exported_paths)} 件",
        title="エクスポートサマリ",
        border_style="green",
    )
    console.print(summary)

    # infra-automation への通知
    if notify:
        console.print("[bold]📢 infra-automation に通知中...[/bold]")
        try:
            # Layer 3 のハイライトを通知
            highlights = [r for r in results if r.layer == Layer.EXPERIMENT]
            if highlights:
                # snippet-collector 経由で通知（MCP 連携）
                console.print(f"[yellow]  通知対象: {len(highlights)} 件の深掘り候補[/yellow]")
                console.print("[dim]  ※ MCP 経由で snippet-collector に保存推奨[/dim]")
            else:
                console.print("[dim]  通知対象なし（深掘り候補なし）[/dim]")
        except Exception as e:
            console.print(f"[red]通知エラー: {e}[/red]")

    # decision-ledger への記録
    if ledger:
        console.print("[bold]📝 decision-ledger に記録中...[/bold]")
        try:
            # Layer 3 の判断を記録
            experiment_results = [r for r in results if r.layer == Layer.EXPERIMENT]
            if experiment_results:
                cnt = len(experiment_results)
                console.print(f"[yellow]  記録対象: {cnt} 件の深掘り判断[/yellow]")
                console.print("[dim]  ※ MCP decision-ledger 経由で記録推奨[/dim]")
            else:
                console.print("[dim]  記録対象なし（深掘り判断なし）[/dim]")
        except Exception as e:
            console.print(f"[red]記録エラー: {e}[/red]")


@app.command()
def marketing(
    trends: bool = typer.Option(True, help="トレンド検知を実行"),
    content: bool = typer.Option(True, help="SNS投稿候補を生成"),
    analytics: bool = typer.Option(False, help="効果測定サマリを表示"),
):
    """
    マーケティング機能

    トレンド検知、SNS投稿候補生成、効果測定連携
    """
    from pathlib import Path

    from evaluators.trend_detector import TrendDetector
    from marketing.analytics import AnalyticsTracker
    from marketing.content_generator import ContentGenerator

    base_dir = Path(__file__).parent.parent
    marketing_dir = base_dir / ".private" / "marketing"

    console.print(Panel("🎯 マーケティング機能", style="bold"))

    # トレンド検知
    if trends:
        console.print("[bold]📈 トレンド検知中...[/bold]")
        detector = TrendDetector(
            data_dir=marketing_dir,
            output_dir=marketing_dir / "trends",
        )
        trend_results = detector.detect_trends()

        rising = trend_results.get("trends", {}).get("rising", [])
        if rising:
            table = Table(title="上昇トレンド")
            table.add_column("キーワード")
            table.add_column("変化")
            table.add_column("前週→今週")

            for t in rising[:5]:
                ratio = t.get("ratio", 0)
                ratio_str = "∞" if ratio == float("inf") else f"{ratio}x"
                table.add_row(
                    t.get("keyword", ""),
                    t.get("change", ""),
                    f"{t.get('prev_count', 0)} → {t.get('current_count', 0)} ({ratio_str})",
                )
            console.print(table)
        else:
            console.print("[dim]  トレンド変化なし[/dim]")

        # 保存
        path = detector.save_trends(trend_results)
        console.print(f"[green]✅ トレンド保存: {path}[/green]")

    # SNS投稿候補生成
    if content:
        console.print()
        console.print("[bold]📝 SNS投稿候補生成中...[/bold]")

        generator = ContentGenerator(output_dir=marketing_dir / "content")

        # トレンドから生成
        if trends:
            candidates = generator.generate_from_trends(trend_results)
        else:
            candidates = []

        # 週次ダイジェストからも生成
        exports_dir = base_dir / "exports"
        import json

        digests = sorted(exports_dir.glob("digest-*.json"), reverse=True)
        if digests:
            week = digests[0].stem.replace("digest-", "")
            with open(digests[0], encoding="utf-8") as f:
                digest_data = json.load(f)
            candidates.extend(generator.generate_from_digest(week, digest_data))

            # 保存
            if candidates:
                path = generator.save_candidates(candidates, week)
                console.print(f"[green]✅ 投稿候補保存: {path}[/green]")

                table = Table(title=f"投稿候補 ({len(candidates)}件)")
                table.add_column("タイプ")
                table.add_column("優先度")
                table.add_column("内容（先頭50文字）")

                for c in candidates[:5]:
                    table.add_row(
                        c.get("type", ""),
                        c.get("priority", ""),
                        c.get("content", "")[:50] + "...",
                    )
                console.print(table)
        else:
            console.print("[dim]  週次ダイジェストがありません[/dim]")

    # 効果測定サマリ
    if analytics:
        console.print()
        console.print("[bold]📊 効果測定サマリ[/bold]")

        tracker = AnalyticsTracker(data_dir=marketing_dir / "analytics")
        summary = tracker.get_performance_summary()

        if summary.get("posts_count", 0) > 0:
            panel = Panel(
                f"📈 過去 {summary.get('period_weeks', 4)} 週間\n"
                f"  • 投稿数: {summary.get('posts_count', 0)}\n"
                f"  • インプレッション: {summary.get('total_impressions', 0)}\n"
                f"  • エンゲージメント率: {summary.get('engagement_rate', 0)}%",
                title="パフォーマンス",
                border_style="blue",
            )
            console.print(panel)
        else:
            console.print("[dim]  効果測定データがありません[/dim]")
            console.print("[dim]  ※ 投稿後に analytics.record_post() で記録してください[/dim]")


if __name__ == "__main__":
    app()
