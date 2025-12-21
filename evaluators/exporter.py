"""
AI Update Radar - エクスポーター

評価結果を他リポジトリ向けにエクスポートする。

出力形式:
- 週次ダイジェスト（JSON）
- 採用決定リスト（YAML）
- 技術アラート（YAML）
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from evaluators.relevance_scorer import EvaluationResult, Layer


@dataclass
class ExportConfig:
    """エクスポート設定"""

    exports_dir: Path
    # Layer 3 のみエクスポート対象
    min_layer: Layer = Layer.EXPERIMENT
    # 採用決定の閾値スコア
    adoption_threshold: float = 8.0
    # アラート対象のキーワード
    alert_keywords: list[str] = field(default_factory=lambda: [
        "breaking change", "deprecation", "deadline", "end of life",
        "security", "vulnerability", "critical",
    ])


class Exporter:
    """評価結果のエクスポーター"""

    def __init__(self, config: Optional[ExportConfig] = None):
        """
        Args:
            config: エクスポート設定（省略時はデフォルト）
        """
        if config is None:
            exports_dir = Path(__file__).parent.parent / "exports"
            config = ExportConfig(exports_dir=exports_dir)

        self.config = config
        self.config.exports_dir.mkdir(parents=True, exist_ok=True)

    def _get_week_string(self) -> str:
        """現在の週を YYYY-WXX 形式で取得"""
        now = datetime.now(timezone.utc)
        return f"{now.year}-W{now.isocalendar()[1]:02d}"

    def _is_alert_candidate(self, result: EvaluationResult) -> bool:
        """アラート候補かどうか判定"""
        text = f"{result.entry.title} {result.entry.summary}".lower()
        return any(kw.lower() in text for kw in self.config.alert_keywords)

    def _determine_target_repo(self, result: EvaluationResult) -> str:
        """対象リポジトリを決定"""
        text = f"{result.entry.title} {result.entry.summary}".lower()

        if any(kw in text for kw in ["mcp", "claude", "anthropic", "tool"]):
            return "infra-automation"
        elif any(kw in text for kw in ["scrim", "fortnite", "esports", "tournament"]):
            return "ScrimAutomationEngine"
        elif any(kw in text for kw in ["stream", "youtube", "twitch", "obs"]):
            return "StreamFlowEngine"
        else:
            return "infra-automation"  # デフォルト

    def export_weekly_digest(
        self,
        results: list[EvaluationResult],
        experiments_completed: Optional[list[dict]] = None,
        adopted: Optional[list[dict]] = None,
    ) -> Path:
        """週次ダイジェストをエクスポート

        Args:
            results: 評価結果リスト
            experiments_completed: 完了した実験リスト
            adopted: 採用決定リスト

        Returns:
            エクスポートファイルのパス
        """
        week = self._get_week_string()

        # Layer 3 のハイライトを抽出
        highlights = []
        for result in results:
            if result.layer.value >= self.config.min_layer.value:
                highlights.append({
                    "title": result.entry.title,
                    "category": result.classification.primary_category.value,
                    "impact": "high" if result.relevance_score >= 8 else "medium",
                    "action": result.decision,
                    "score": round(result.relevance_score, 1),
                    "details_url": result.entry.url,
                })

        digest = {
            "week": week,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_evaluated": len(results),
                "layer_3_count": sum(1 for r in results if r.layer == Layer.EXPERIMENT),
                "layer_2_count": sum(1 for r in results if r.layer == Layer.DETECT),
                "layer_1_count": sum(1 for r in results if r.layer == Layer.IGNORE),
            },
            "highlights": highlights,
            "experiments_completed": experiments_completed or [],
            "adopted": adopted or [],
        }

        # ファイル出力
        output_path = self.config.exports_dir / f"digest-{week}.json"
        with open(output_path, "w") as f:
            json.dump(digest, f, indent=2, ensure_ascii=False)

        return output_path

    def export_adopted_list(self, results: list[EvaluationResult]) -> Path:
        """採用決定リストをエクスポート

        Args:
            results: 評価結果リスト

        Returns:
            エクスポートファイルのパス
        """
        week = self._get_week_string()
        date_str = datetime.now().strftime("%Y-%m-%d")

        adopted_items = []
        for result in results:
            if result.relevance_score >= self.config.adoption_threshold:
                adopted_items.append({
                    "id": f"{date_str}-{hash(result.entry.url) % 10000:04d}",
                    "title": result.entry.title,
                    "target_repo": self._determine_target_repo(result),
                    "action": result.next_action,
                    "priority": "high" if result.relevance_score >= 9 else "medium",
                    "score": round(result.relevance_score, 1),
                    "url": result.entry.url,
                })

        data = {
            "week": week,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "adopted": adopted_items,
        }

        output_path = self.config.exports_dir / f"adopted-{week}.yaml"
        with open(output_path, "w") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return output_path

    def export_alerts(self, results: list[EvaluationResult]) -> Path:
        """技術アラートをエクスポート

        Args:
            results: 評価結果リスト

        Returns:
            エクスポートファイルのパス
        """
        week = self._get_week_string()

        alerts = []
        for result in results:
            if self._is_alert_candidate(result):
                # アラートタイプを推定
                text = f"{result.entry.title} {result.entry.summary}".lower()
                if "breaking" in text or "deprecat" in text:
                    alert_type = "breaking_change"
                elif "security" in text or "vulnerab" in text:
                    alert_type = "security"
                elif "deadline" in text or "end of life" in text:
                    alert_type = "deadline"
                else:
                    alert_type = "notice"

                alerts.append({
                    "type": alert_type,
                    "source": result.entry.source_name,
                    "title": result.entry.title,
                    "message": result.entry.summary[:200] if result.entry.summary else "",
                    "url": result.entry.url,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                })

        data = {
            "week": week,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "alerts": alerts,
        }

        output_path = self.config.exports_dir / f"alerts-{week}.yaml"
        with open(output_path, "w") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return output_path

    def export_all(
        self,
        results: list[EvaluationResult],
        experiments_completed: Optional[list[dict]] = None,
        adopted: Optional[list[dict]] = None,
    ) -> dict[str, Path]:
        """全形式でエクスポート

        Args:
            results: 評価結果リスト
            experiments_completed: 完了した実験リスト
            adopted: 既存の採用決定リスト

        Returns:
            出力ファイルパスの辞書
        """
        return {
            "digest": self.export_weekly_digest(results, experiments_completed, adopted),
            "adopted": self.export_adopted_list(results),
            "alerts": self.export_alerts(results),
        }


if __name__ == "__main__":
    # テスト
    from collectors.models import CollectedEntry, SourceType
    from evaluators.relevance_scorer import RelevanceScorer

    scorer = RelevanceScorer()
    exporter = Exporter()

    test_entries = [
        CollectedEntry(
            title="MCP Protocol v2 with breaking changes",
            url="https://example.com/mcp",
            source_name="Test",
            source_type=SourceType.RSS,
            summary="New MCP protocol with breaking changes, deprecation notice",
        ),
        CollectedEntry(
            title="Claude API pricing reduced by 50%",
            url="https://example.com/claude",
            source_name="Test",
            source_type=SourceType.RSS,
            summary="Major price reduction for Claude API",
        ),
    ]

    print("=== Exporter Test ===\n")

    # 評価
    results = scorer.evaluate_batch(test_entries)

    # エクスポート
    paths = exporter.export_all(results)

    for name, path in paths.items():
        print(f"{name}: {path}")
        with open(path) as f:
            print(f.read()[:500])
        print()
