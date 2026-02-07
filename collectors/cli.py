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
from collectors.models import Category, CollectedEntry, CollectionResult
from collectors.page_diff_collector import PageDiffCollector
from collectors.rss_collector import RSSCollector
from collectors.zenn_collector import ZennCollector
from evaluators.article_evaluator import ArticleEvaluator, EvaluationResult

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
def zenn(
    days: int = typer.Option(7, help="過去N日分を収集"),
    export: bool = typer.Option(False, help="JSON にエクスポート"),
    min_score: Optional[int] = typer.Option(None, help="最低スコア（None で設定値を使用、-999 で全件）"),
    output: Optional[str] = typer.Option(None, help="エクスポート先ファイル名"),
):
    """
    Zenn 記事を収集（段階フィルター方式 ①）

    トピック別 RSS から記事を収集し、soft filter でスコア付け
    """
    sources_dir, cache_dir, keywords_path, exports_dir = get_paths()

    since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    since = since - timedelta(days=days)

    console.print("[bold]📰 Zenn 記事収集中...[/bold]")

    collector = ZennCollector(
        sources_dir=sources_dir,
        cache_dir=cache_dir,
        keywords_path=keywords_path,
    )

    result = collector.collect(since=since, min_score=min_score)

    # 結果表示
    if result.entries:
        # スコア順でソート
        def get_score(entry: CollectedEntry) -> int:
            try:
                data = json.loads(entry.raw_content)
                return data.get("prefilter_score", 0)
            except (json.JSONDecodeError, TypeError):
                return 0

        sorted_entries = sorted(result.entries, key=get_score, reverse=True)

        table = Table(title=f"Zenn 記事 ({len(sorted_entries)} 件)")
        table.add_column("日付", style="dim", width=6)
        table.add_column("スコア", width=5, justify="right")
        table.add_column("タイトル", width=50)
        table.add_column("トピック", width=10)
        table.add_column("マッチ", style="cyan", width=20)

        for entry in sorted_entries[:30]:
            date_str = entry.published_at.strftime("%m/%d") if entry.published_at else "-"
            try:
                filter_data = json.loads(entry.raw_content)
                score = filter_data.get("prefilter_score", 0)
                topic = filter_data.get("source_topic", "")
                matched = ", ".join(filter_data.get("boost_matched", [])[:3])
            except (json.JSONDecodeError, TypeError):
                score = 0
                topic = ""
                matched = ""

            score_style = "green" if score >= 2 else "yellow" if score >= 0 else "red"
            table.add_row(
                date_str,
                f"[{score_style}]{score}[/{score_style}]",
                entry.title[:50],
                topic,
                matched,
            )

        console.print(table)
    else:
        console.print("[dim]新しい記事はありません[/dim]")

    # エラー表示
    for err in result.errors:
        console.print(f"[red]Error: {err}[/red]")

    # サマリ
    summary_panel = Panel(
        f"📊 収集完了\n"
        f"  • 記事: {len(result.entries)} 件\n"
        f"  • エラー: {len(result.errors)} 件\n"
        f"  • 期間: 過去 {days} 日",
        title="Zenn 収集サマリ",
        border_style="green" if not result.errors else "yellow",
    )
    console.print(summary_panel)

    # エクスポート
    if export:
        exports_dir.mkdir(parents=True, exist_ok=True)
        if output:
            export_path = exports_dir / output
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = exports_dir / f"zenn_{timestamp}.json"

        export_data = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "days": days,
            "min_score": min_score,
            "result": result.to_dict(),
        }

        with open(export_path, "w") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        console.print(f"[green]✅ エクスポート完了: {export_path}[/green]")


@app.command(name="evaluate-articles")
def evaluate_articles(
    days: Optional[int] = typer.Option(None, help="Zenn 記事を収集してから評価（過去N日分）"),
    input_file: Optional[str] = typer.Option(None, "--input", help="既存エクスポート JSON を入力"),
    output: Optional[str] = typer.Option(None, help="出力ファイル名"),
    min_score: Optional[int] = typer.Option(None, help="Zenn 収集時の最低スコア"),
):
    """
    Zenn 記事を AI 評価（段階フィルター方式 ②）

    send_consultation 経由で LLM に記事を評価させる。
    --days: Zenn 収集 + 評価のワンショット
    --input: 既存エクスポート JSON を入力として評価
    """
    sources_dir, cache_dir, keywords_path, exports_dir = get_paths()

    if days is None and input_file is None:
        console.print("[red]--days または --input のいずれかを指定してください[/red]")
        raise typer.Exit(1)

    entries = []

    if input_file:
        # 既存 JSON から読み込み
        import_path = exports_dir / input_file if not Path(input_file).is_absolute() else Path(input_file)
        if not import_path.exists():
            console.print(f"[red]ファイルが見つかりません: {import_path}[/red]")
            raise typer.Exit(1)

        console.print(f"[bold]📂 {import_path.name} から読み込み中...[/bold]")
        with open(import_path) as f:
            data = json.load(f)

        # zenn コマンドのエクスポート形式から CollectedEntry を復元
        result_data = data.get("result", {})
        for entry_data in result_data.get("entries", []):
            entries.append(CollectedEntry.from_dict(entry_data))

    else:
        # Zenn 記事を収集
        since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        since = since - timedelta(days=days)

        console.print(f"[bold]📰 Zenn 記事収集中（過去 {days} 日）...[/bold]")
        collector = ZennCollector(
            sources_dir=sources_dir,
            cache_dir=cache_dir,
            keywords_path=keywords_path,
        )
        result = collector.collect(since=since, min_score=min_score)
        entries = result.entries

        if result.errors:
            for err in result.errors:
                console.print(f"[yellow]Warning: {err}[/yellow]")

    if not entries:
        console.print("[dim]評価対象の記事がありません[/dim]")
        raise typer.Exit(0)

    console.print(f"[bold]🔍 {len(entries)} 件を AI 評価中...[/bold]")

    # send_consultation 関数を注入
    # MCP 経由で呼び出す場合は外部から send_fn を注入する想定
    # CLI 単体では send_fn が None → エラーメッセージを表示
    send_fn = _get_send_fn()
    if send_fn is None:
        console.print("[red]send_consultation が利用できません。[/red]")
        console.print("[dim]SEND_CONSULTATION_URL を設定してください（MCP gateway 経由で LLM 評価を実行）[/dim]")
        raise typer.Exit(1)

    evaluator = ArticleEvaluator(send_fn=send_fn)
    eval_result = evaluator.evaluate_batch(entries)

    # 結果表示
    if eval_result.evaluations:
        # relevance 降順でソート
        sorted_evals = sorted(
            eval_result.evaluations,
            key=lambda e: (e.relevance, e.actionability),
            reverse=True,
        )

        table = Table(title=f"AI 評価結果 ({len(sorted_evals)} 件)")
        table.add_column("関連性", width=5, justify="center")
        table.add_column("実用性", width=5, justify="center")
        table.add_column("判定", width=6)
        table.add_column("タイトル", width=40)
        table.add_column("要約", width=25)
        table.add_column("元", width=4)

        action_styles = {
            "adopt": "bold green",
            "watch": "yellow",
            "skip": "dim",
        }

        for ev in sorted_evals[:30]:
            rel_style = "green" if ev.relevance >= 4 else "yellow" if ev.relevance >= 3 else "dim"
            act_style = action_styles.get(ev.recommended_action, "")
            src_mark = "LLM" if ev.evaluation_source == "llm" else "FB"
            table.add_row(
                f"[{rel_style}]{ev.relevance}[/{rel_style}]",
                f"{ev.actionability}",
                f"[{act_style}]{ev.recommended_action}[/{act_style}]",
                ev.title[:40],
                ev.summary_ja[:25],
                src_mark,
            )

        console.print(table)

    # サマリ
    adopt_count = sum(1 for e in eval_result.evaluations if e.recommended_action == "adopt")
    watch_count = sum(1 for e in eval_result.evaluations if e.recommended_action == "watch")
    skip_count = sum(1 for e in eval_result.evaluations if e.recommended_action == "skip")

    summary_panel = Panel(
        f"📊 AI 評価完了\n"
        f"  • 評価: {eval_result.total} 件（LLM: {eval_result.llm_evaluated}, フォールバック: {eval_result.fallback_used}）\n"
        f"  • 採用推奨: [bold green]{adopt_count}[/bold green] 件\n"
        f"  • 注視: [yellow]{watch_count}[/yellow] 件\n"
        f"  • スキップ: [dim]{skip_count}[/dim] 件",
        title="評価サマリ",
        border_style="green",
    )
    console.print(summary_panel)

    # エクスポート
    exports_dir.mkdir(parents=True, exist_ok=True)
    if output:
        export_path = exports_dir / output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = exports_dir / f"article_evaluations_{timestamp}.json"

    with open(export_path, "w") as f:
        json.dump(eval_result.to_dict(), f, indent=2, ensure_ascii=False)

    console.print(f"[green]✅ 評価結果エクスポート: {export_path}[/green]")


def _get_send_fn():
    """send_consultation 関数を取得（MCP 経由）

    環境変数 SEND_CONSULTATION_URL が設定されていれば HTTP 経由で呼び出す。
    未設定の場合は None を返す（フォールバック評価のみ可能）。
    """
    url = os.environ.get("SEND_CONSULTATION_URL")
    if not url:
        return None

    import urllib.request

    def send_fn(situation: str, options: list, question: str, consultation_type: str) -> str:
        payload = json.dumps({
            "situation": situation,
            "options": options,
            "question": question,
            "consultation_type": consultation_type,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("response", result.get("result", ""))

    return send_fn


def _post_to_mastodon(articles: list[dict]) -> list[dict]:
    """Mastodon に記事を投稿"""
    api_url = os.environ.get("MASTODON_API_URL")
    token = os.environ.get("MASTODON_ACCESS_TOKEN")
    if not api_url or not token:
        return []

    import urllib.request

    results = []
    for article in articles:
        status = (
            f"📰 {article['title']}\n\n"
            f"{article.get('summary_ja', '')}\n\n"
            f"関連性: {'⭐' * article.get('relevance', 0)}\n"
            f"{article['url']}\n\n"
            f"#AI #自動化 #技術記事"
        )

        payload = json.dumps({"status": status, "visibility": "unlisted"}).encode("utf-8")
        req = urllib.request.Request(
            f"{api_url}/api/v1/statuses",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                results.append({"url": article["url"], "toot_id": result.get("id"), "success": True})
        except Exception as e:
            results.append({"url": article["url"], "success": False, "error": str(e)})

    return results


@app.command(name="notify-articles")
def notify_articles(
    input_file: Optional[str] = typer.Option(None, "--input", help="記事候補 JSON（article_candidates.json）"),
    decisions_file: Optional[str] = typer.Option(None, "--decisions", help="承認結果 JSON（article_decisions.json）"),
    dry_run: bool = typer.Option(False, help="投稿せず表示のみ"),
):
    """
    承認済み記事を通知（段階フィルター方式 ③）

    --input: AI 評価結果 JSON
    --decisions: フロントエンドからエクスポートした承認結果 JSON
    Mastodon に投稿する場合は MASTODON_API_URL と MASTODON_ACCESS_TOKEN を設定
    """
    base_dir = Path(__file__).parent.parent
    default_candidates_path = base_dir / "frontend" / "public" / "data" / "article_candidates.json"

    # 1. article_candidates.json を読み込む
    if input_file:
        candidates_path = Path(input_file) if Path(input_file).is_absolute() else base_dir / input_file
    else:
        candidates_path = default_candidates_path

    if not candidates_path.exists():
        console.print(f"[red]ファイルが見つかりません: {candidates_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]📂 記事候補を読み込み中: {candidates_path.name}[/bold]")
    try:
        with open(candidates_path) as f:
            candidates_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        console.print(f"[red]読み込みエラー: {e}[/red]")
        raise typer.Exit(1)

    # candidates_data は list または dict（evaluations キー付き）
    if isinstance(candidates_data, list):
        all_candidates = candidates_data
    elif isinstance(candidates_data, dict):
        all_candidates = candidates_data.get("evaluations", candidates_data.get("articles", []))
    else:
        all_candidates = []

    # 2. decisions を読み込み、承認済み記事を決定
    approved_articles = []

    if decisions_file:
        decisions_path = Path(decisions_file) if Path(decisions_file).is_absolute() else base_dir / decisions_file
        if not decisions_path.exists():
            console.print(f"[red]承認結果ファイルが見つかりません: {decisions_path}[/red]")
            raise typer.Exit(1)

        console.print(f"[bold]📋 承認結果を読み込み中: {decisions_path.name}[/bold]")
        try:
            with open(decisions_path) as f:
                decisions_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            console.print(f"[red]承認結果の読み込みエラー: {e}[/red]")
            raise typer.Exit(1)

        approved_articles = decisions_data.get("approved", [])
        console.print(f"[dim]  承認日時: {decisions_data.get('exported_at', '不明')}[/dim]")
    else:
        # decisions がない場合は recommended_action == "adopt" の記事を自動選択
        console.print("[dim]承認結果なし → recommended_action == 'adopt' の記事を自動選択[/dim]")
        for article in all_candidates:
            if article.get("recommended_action") == "adopt":
                approved_articles.append(article)

    if not approved_articles:
        console.print("[yellow]承認済み記事がありません[/yellow]")
        raise typer.Exit(0)

    # 3. 承認済み記事をテーブル表示
    table = Table(title=f"承認済み記事 ({len(approved_articles)} 件)")
    table.add_column("関連性", width=5, justify="center")
    table.add_column("タイトル", width=45)
    table.add_column("判定", width=6)
    table.add_column("投稿", width=6)

    # 4. Mastodon 投稿
    post_results = []
    if not dry_run:
        api_url = os.environ.get("MASTODON_API_URL")
        token = os.environ.get("MASTODON_ACCESS_TOKEN")
        if api_url and token:
            console.print("[bold]📤 Mastodon に投稿中...[/bold]")
            post_results = _post_to_mastodon(approved_articles)
        else:
            console.print("[dim]Mastodon 環境変数未設定（MASTODON_API_URL, MASTODON_ACCESS_TOKEN）→ 投稿スキップ[/dim]")
    else:
        console.print("[yellow]dry-run モード: 投稿をスキップ[/yellow]")

    # 投稿結果をルックアップ用に変換
    post_result_map = {r["url"]: r for r in post_results}

    # テーブルに行を追加
    success_count = 0
    error_count = 0
    for article in approved_articles:
        relevance = article.get("relevance", 0)
        rel_style = "green" if relevance >= 4 else "yellow" if relevance >= 3 else "dim"
        action = article.get("recommended_action", "-")

        # 投稿結果
        pr = post_result_map.get(article.get("url", ""))
        if pr:
            if pr.get("success"):
                post_status = "[green]OK[/green]"
                success_count += 1
            else:
                post_status = "[red]NG[/red]"
                error_count += 1
        elif dry_run:
            post_status = "[dim]skip[/dim]"
        else:
            post_status = "[dim]-[/dim]"

        table.add_row(
            f"[{rel_style}]{relevance}[/{rel_style}]",
            article.get("title", "")[:45],
            action,
            post_status,
        )

    console.print(table)

    # 5. サマリ表示
    summary_parts = [
        f"📊 通知完了",
        f"  • 承認記事: {len(approved_articles)} 件",
    ]
    if post_results:
        summary_parts.append(f"  • 投稿成功: [green]{success_count}[/green] 件")
        if error_count > 0:
            summary_parts.append(f"  • 投稿エラー: [red]{error_count}[/red] 件")
    elif dry_run:
        summary_parts.append(f"  • 投稿: dry-run（スキップ）")
    else:
        summary_parts.append(f"  • 投稿: 環境変数未設定（スキップ）")

    border_style = "green" if error_count == 0 else "yellow"
    summary_panel = Panel(
        "\n".join(summary_parts),
        title="通知サマリ",
        border_style=border_style,
    )
    console.print(summary_panel)


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
