"""
AI Update Radar - 判断ログ出力

評価結果を YAML 形式でログ出力する。
出力先: .private/logs/evaluations/
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from evaluators.relevance_scorer import EvaluationResult, Layer


class EvaluationLogger:
    """評価結果のロガー"""

    def __init__(self, log_dir: Optional[Path] = None):
        """
        Args:
            log_dir: ログ出力ディレクトリ（省略時はデフォルト）
        """
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / ".private" / "logs" / "evaluations"

        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _result_to_dict(self, result: EvaluationResult) -> dict:
        """評価結果を辞書に変換"""
        return {
            "entry": {
                "title": result.entry.title,
                "url": result.entry.url,
                "source": result.entry.source_name,
                "source_type": result.entry.source_type.value,
                "published_at": (
                    result.entry.published_at.isoformat()
                    if result.entry.published_at
                    else None
                ),
            },
            "evaluation": {
                "category": result.classification.primary_category.value,
                "confidence": round(result.classification.confidence, 2),
                "matched_keywords": result.classification.matched_keywords[:5],
                "relevance_score": round(result.relevance_score, 1),
                "layer": result.layer.value,
                "scoring_breakdown": {
                    "applicability": result.scoring.applicability,
                    "cost_reduction": result.scoring.cost_reduction,
                    "risk": result.scoring.risk,
                    "urgency": result.scoring.urgency,
                },
                "decision": result.decision,
                "reason": result.reason,
                "next_action": result.next_action,
            },
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

    def log_single(self, result: EvaluationResult) -> Path:
        """単一の評価結果をログ

        Args:
            result: 評価結果

        Returns:
            ログファイルのパス
        """
        data = self._result_to_dict(result)

        # ファイル名: {date}_{layer}_{hash}.yaml
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        url_hash = hash(result.entry.url) % 10000
        filename = f"{date_str}_{result.layer.name.lower()}_{url_hash:04d}.yaml"

        log_path = self.log_dir / filename

        with open(log_path, "w") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return log_path

    def log_batch(self, results: list[EvaluationResult]) -> Path:
        """複数の評価結果をまとめてログ

        Args:
            results: 評価結果リスト

        Returns:
            ログファイルのパス
        """
        if not results:
            return self.log_dir

        # レイヤー別に集計
        by_layer = {
            Layer.EXPERIMENT: [],
            Layer.DETECT: [],
            Layer.IGNORE: [],
        }

        for result in results:
            by_layer[result.layer].append(self._result_to_dict(result))

        data = {
            "summary": {
                "total": len(results),
                "experiment": len(by_layer[Layer.EXPERIMENT]),
                "detect": len(by_layer[Layer.DETECT]),
                "ignore": len(by_layer[Layer.IGNORE]),
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            },
            "experiment": by_layer[Layer.EXPERIMENT],
            "detect": by_layer[Layer.DETECT],
            "ignore": by_layer[Layer.IGNORE],
        }

        # ファイル名
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"batch_{date_str}.yaml"
        log_path = self.log_dir / filename

        with open(log_path, "w") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return log_path

    def get_recent_logs(self, days: int = 7, layer: Optional[Layer] = None) -> list[dict]:
        """最近のログを取得

        Args:
            days: 過去N日分
            layer: フィルタするレイヤー

        Returns:
            ログデータのリスト
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        results = []

        for log_file in sorted(self.log_dir.glob("*.yaml"), reverse=True):
            # ファイル名から日付を推測
            try:
                date_str = log_file.stem.split("_")[0]
                if len(date_str) == 8:  # YYYYMMDD
                    file_date = datetime.strptime(date_str, "%Y%m%d")
                    file_date = file_date.replace(tzinfo=timezone.utc)
                    if file_date < cutoff:
                        continue
            except (ValueError, IndexError):
                continue

            with open(log_file) as f:
                data = yaml.safe_load(f)

            if data:
                # バッチログの場合
                if "summary" in data:
                    if layer:
                        layer_key = layer.name.lower()
                        results.extend(data.get(layer_key, []))
                    else:
                        for key in ["experiment", "detect", "ignore"]:
                            results.extend(data.get(key, []))
                else:
                    # 単一ログ
                    if layer:
                        if data.get("evaluation", {}).get("layer") == layer.value:
                            results.append(data)
                    else:
                        results.append(data)

        return results

    def generate_summary_report(self, days: int = 7) -> str:
        """サマリレポートを生成

        Args:
            days: 過去N日分

        Returns:
            Markdown 形式のレポート
        """
        logs = self.get_recent_logs(days)

        if not logs:
            return f"# 評価サマリ（過去 {days} 日間）\n\nデータなし"

        # 集計
        by_layer = {"experiment": [], "detect": [], "ignore": []}
        by_category = {}

        for log in logs:
            eval_data = log.get("evaluation", {})
            layer = eval_data.get("decision", "ignore")
            category = eval_data.get("category", "other")

            by_layer.get(layer, by_layer["ignore"]).append(log)
            by_category[category] = by_category.get(category, 0) + 1

        # レポート生成
        lines = [
            f"# 評価サマリ（過去 {days} 日間）",
            "",
            "## 概要",
            "",
            f"- 総数: {len(logs)} 件",
            f"- 深掘り対象 (Layer 3): {len(by_layer['experiment'])} 件",
            f"- 検知のみ (Layer 2): {len(by_layer['detect'])} 件",
            f"- 無視 (Layer 1): {len(by_layer['ignore'])} 件",
            "",
            "## カテゴリ別",
            "",
        ]

        for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
            lines.append(f"- {cat}: {count} 件")

        # 深掘り対象の詳細
        if by_layer["experiment"]:
            lines.extend([
                "",
                "## 深掘り対象 (Layer 3)",
                "",
            ])
            for log in by_layer["experiment"][:10]:  # 最大10件
                entry = log.get("entry", {})
                eval_data = log.get("evaluation", {})
                lines.append(f"### {entry.get('title', 'N/A')}")
                lines.append(f"- URL: {entry.get('url', 'N/A')}")
                lines.append(f"- スコア: {eval_data.get('relevance_score', 0)}")
                lines.append(f"- 理由: {eval_data.get('reason', 'N/A')}")
                lines.append(f"- 次のアクション: {eval_data.get('next_action', 'N/A')}")
                lines.append("")

        return "\n".join(lines)


if __name__ == "__main__":
    # テスト
    from collectors.models import CollectedEntry, SourceType
    from evaluators.relevance_scorer import RelevanceScorer

    scorer = RelevanceScorer()
    logger = EvaluationLogger()

    test_entries = [
        CollectedEntry(
            title="MCP Protocol v2 with Python SDK",
            url="https://example.com/mcp",
            source_name="Test",
            source_type=SourceType.RSS,
            summary="New Model Context Protocol with Discord integration",
        ),
        CollectedEntry(
            title="Claude pricing update",
            url="https://example.com/claude",
            source_name="Test",
            source_type=SourceType.RSS,
            summary="Price reduction announced",
        ),
    ]

    print("=== Evaluation Logger Test ===\n")

    # 評価
    results = scorer.evaluate_batch(test_entries)

    # バッチログ
    log_path = logger.log_batch(results)
    print(f"Batch log saved: {log_path}")

    # 単一ログ
    for result in results:
        single_path = logger.log_single(result)
        print(f"Single log saved: {single_path}")

    # サマリレポート
    print("\n" + "=" * 50)
    print(logger.generate_summary_report(days=1))
