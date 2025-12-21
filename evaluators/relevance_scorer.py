"""
AI Update Radar - 関連性スコアラー

収集したエントリの関連性をスコアリングし、Layer 判定を行う。
スコアリング要素:
- applicability: 直接適用可能性（今のシステムにそのまま入るか）
- cost_reduction: コスト削減（時間 or 費用の削減が見込めるか）
- risk: リスク（導入リスクは低いか）
- urgency: 緊急性（競合優位性に影響するか）
"""

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Optional

from collectors.models import Category, CollectedEntry
from evaluators.category_classifier import CategoryClassifier, ClassificationResult


class Layer(IntEnum):
    """評価レイヤー"""

    IGNORE = 1  # 無視（スコア 0-3）
    DETECT = 2  # 検知のみ（スコア 4-6）
    EXPERIMENT = 3  # 深掘り対象（スコア 7+）


@dataclass
class ScoringBreakdown:
    """スコアリング内訳"""

    applicability: int = 0  # 直接適用可能性 (0-10)
    cost_reduction: int = 0  # コスト削減 (0-10)
    risk: int = 0  # 低リスク度 (0-10, 高いほど低リスク)
    urgency: int = 0  # 緊急性 (0-10)

    @property
    def total(self) -> float:
        """加重平均スコア"""
        # applicability を重視（40%）、その他は各20%
        return (
            self.applicability * 0.4
            + self.cost_reduction * 0.2
            + self.risk * 0.2
            + self.urgency * 0.2
        )


@dataclass
class EvaluationResult:
    """評価結果"""

    entry: CollectedEntry
    classification: ClassificationResult
    scoring: ScoringBreakdown
    layer: Layer
    relevance_score: float  # 0.0-10.0
    decision: str  # ignore / detect / experiment
    reason: str = ""
    next_action: str = ""


class RelevanceScorer:
    """関連性スコアラー"""

    # カテゴリ別ベーススコア（重要度の基本値）
    CATEGORY_BASE_SCORES = {
        Category.CAPABILITY: {"applicability": 6, "cost_reduction": 5, "urgency": 7},
        Category.CONSTRAINT: {"applicability": 7, "cost_reduction": 6, "urgency": 5},
        Category.PRICING: {"applicability": 8, "cost_reduction": 8, "urgency": 4},
        Category.OTHER: {"applicability": 3, "cost_reduction": 2, "urgency": 2},
    }

    # 高評価キーワード（マッチするとスコア加算）
    HIGH_IMPACT_KEYWORDS = {
        # 直接適用可能性を高める
        "applicability": [
            "mcp",
            "claude code",
            "api",
            "sdk",
            "python",
            "fastapi",
            "discord",
            "bot",
        ],
        # コスト削減を高める
        "cost_reduction": [
            "free",
            "cheaper",
            "reduction",
            "discount",
            "credits",
            "batch",
            "cache",
        ],
        # リスクを下げる（スコア上昇）
        "risk": [
            "stable",
            "production",
            "enterprise",
            "tested",
            "backward compatible",
        ],
        # 緊急性を高める
        "urgency": [
            "breaking change",
            "deprecation",
            "deadline",
            "limited time",
            "competition",
        ],
    }

    # 低評価キーワード（マッチするとスコア減少）
    LOW_IMPACT_KEYWORDS = {
        "applicability": ["ios", "android", "mobile", "unity", "game engine"],
        "cost_reduction": ["increase", "expensive", "premium only"],
        "risk": ["beta", "preview", "experimental", "unstable", "alpha"],
        "urgency": ["future", "roadmap", "planned", "upcoming"],
    }

    def __init__(
        self,
        classifier: Optional[CategoryClassifier] = None,
        keywords_path: Optional[Path] = None,
    ):
        """
        Args:
            classifier: カテゴリ分類器（省略時は新規作成）
            keywords_path: keywords.yaml のパス
        """
        self.classifier = classifier or CategoryClassifier(keywords_path)

    def _get_text(self, entry: CollectedEntry) -> str:
        """エントリからスコアリング対象テキストを取得"""
        return f"{entry.title} {entry.summary} {entry.raw_content}".lower()

    def _count_keyword_matches(self, text: str, keywords: list[str]) -> int:
        """キーワードマッチ数をカウント"""
        count = 0
        for kw in keywords:
            if kw.lower() in text:
                count += 1
        return count

    def _calculate_scores(
        self, entry: CollectedEntry, classification: ClassificationResult
    ) -> ScoringBreakdown:
        """スコアリング内訳を計算"""
        text = self._get_text(entry)

        # ベーススコア取得
        base = self.CATEGORY_BASE_SCORES.get(
            classification.primary_category,
            {"applicability": 5, "cost_reduction": 5, "urgency": 5},
        )

        # 各要素のスコア計算
        scores = ScoringBreakdown()

        for attr in ["applicability", "cost_reduction", "risk", "urgency"]:
            # ベーススコア
            score = base.get(attr, 5)

            # 高評価キーワードでプラス
            high_matches = self._count_keyword_matches(
                text, self.HIGH_IMPACT_KEYWORDS.get(attr, [])
            )
            score += min(high_matches * 2, 4)  # 最大+4

            # 低評価キーワードでマイナス
            low_matches = self._count_keyword_matches(
                text, self.LOW_IMPACT_KEYWORDS.get(attr, [])
            )
            score -= min(low_matches * 2, 4)  # 最大-4

            # 分類信頼度による調整
            score = int(score * (0.7 + 0.3 * classification.confidence))

            # 0-10 にクランプ
            setattr(scores, attr, max(0, min(10, score)))

        return scores

    def _determine_layer(self, score: float, is_ignored: bool) -> Layer:
        """スコアからレイヤーを決定"""
        if is_ignored:
            return Layer.IGNORE

        if score >= 7:
            return Layer.EXPERIMENT
        elif score >= 4:
            return Layer.DETECT
        else:
            return Layer.IGNORE

    def _generate_reason(
        self,
        entry: CollectedEntry,
        classification: ClassificationResult,
        scoring: ScoringBreakdown,
        layer: Layer,
    ) -> str:
        """評価理由を生成"""
        if classification.is_ignored:
            return f"無視キーワード検出: {', '.join(classification.matched_keywords[:3])}"

        reasons = []

        # カテゴリ説明
        cat_desc = {
            Category.CAPABILITY: "能力変化",
            Category.CONSTRAINT: "制限解除",
            Category.PRICING: "価格変化",
            Category.OTHER: "その他",
        }
        reasons.append(f"カテゴリ: {cat_desc.get(classification.primary_category, '不明')}")

        # スコアリングのハイライト
        if scoring.applicability >= 7:
            reasons.append("直接適用可能性が高い")
        if scoring.cost_reduction >= 7:
            reasons.append("コスト削減効果が見込める")
        if scoring.urgency >= 7:
            reasons.append("緊急性が高い")
        if scoring.risk >= 7:
            reasons.append("導入リスクが低い")

        # マッチしたキーワード
        if classification.matched_keywords:
            kws = ", ".join(classification.matched_keywords[:3])
            reasons.append(f"キーワード: {kws}")

        return "。".join(reasons)

    def _suggest_next_action(
        self, entry: CollectedEntry, layer: Layer, classification: ClassificationResult
    ) -> str:
        """次のアクションを提案"""
        if layer == Layer.EXPERIMENT:
            # 実験ディレクトリ名を提案
            from datetime import datetime

            date_str = datetime.now().strftime("%Y-%m-%d")
            # タイトルから簡易的な名前を生成
            name = entry.title[:30].lower()
            name = "".join(c if c.isalnum() else "-" for c in name)
            name = "-".join(filter(None, name.split("-")))[:30]
            return f"experiments/{date_str}-{name}/"
        elif layer == Layer.DETECT:
            return "週次サマリに記載"
        else:
            return "記録のみ"

    def evaluate(self, entry: CollectedEntry) -> EvaluationResult:
        """エントリを評価

        Args:
            entry: 評価対象のエントリ

        Returns:
            評価結果
        """
        # カテゴリ分類
        classification = self.classifier.classify(entry)

        # 無視対象の場合
        if classification.is_ignored:
            return EvaluationResult(
                entry=entry,
                classification=classification,
                scoring=ScoringBreakdown(),
                layer=Layer.IGNORE,
                relevance_score=0.0,
                decision="ignore",
                reason=self._generate_reason(
                    entry, classification, ScoringBreakdown(), Layer.IGNORE
                ),
                next_action="なし",
            )

        # スコアリング
        scoring = self._calculate_scores(entry, classification)
        relevance_score = scoring.total

        # レイヤー判定
        layer = self._determine_layer(relevance_score, classification.is_ignored)

        # 決定
        decision = {
            Layer.IGNORE: "ignore",
            Layer.DETECT: "detect",
            Layer.EXPERIMENT: "experiment",
        }[layer]

        return EvaluationResult(
            entry=entry,
            classification=classification,
            scoring=scoring,
            layer=layer,
            relevance_score=relevance_score,
            decision=decision,
            reason=self._generate_reason(entry, classification, scoring, layer),
            next_action=self._suggest_next_action(entry, layer, classification),
        )

    def evaluate_batch(self, entries: list[CollectedEntry]) -> list[EvaluationResult]:
        """複数エントリを一括評価"""
        return [self.evaluate(entry) for entry in entries]


if __name__ == "__main__":
    # テスト
    from collectors.models import SourceType

    scorer = RelevanceScorer()

    test_entries = [
        CollectedEntry(
            title="MCP Protocol v2 released with Python SDK",
            url="https://example.com/1",
            source_name="Test",
            source_type=SourceType.RSS,
            summary="New Model Context Protocol version with stable API and Discord integration",
        ),
        CollectedEntry(
            title="Claude API pricing reduced by 40%",
            url="https://example.com/2",
            source_name="Test",
            source_type=SourceType.RSS,
            summary="Anthropic announces significant price reduction for all tiers",
        ),
        CollectedEntry(
            title="GPT-5 beta preview announced",
            url="https://example.com/3",
            source_name="Test",
            source_type=SourceType.RSS,
            summary="OpenAI reveals upcoming model in experimental preview",
        ),
        CollectedEntry(
            title="Mobile SDK tutorial for beginners",
            url="https://example.com/4",
            source_name="Test",
            source_type=SourceType.RSS,
            summary="Getting started with iOS and Android integration",
        ),
    ]

    print("=== Relevance Scorer Test ===\n")

    for entry in test_entries:
        result = scorer.evaluate(entry)
        print(f"Title: {entry.title}")
        print(f"  Category: {result.classification.primary_category.value}")
        print(f"  Score: {result.relevance_score:.1f}")
        print(f"  Layer: {result.layer.name} ({result.decision})")
        print(f"  Scoring: A={result.scoring.applicability} C={result.scoring.cost_reduction} "
              f"R={result.scoring.risk} U={result.scoring.urgency}")
        print(f"  Reason: {result.reason}")
        print(f"  Next: {result.next_action}")
        print()
