"""
AI Update Radar - カテゴリ分類器

収集したエントリをキーワードベースでカテゴリ分類する。
カテゴリ: capability（能力変化）, constraint（制限解除）, pricing（価格変化）, other
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from collectors.models import Category, CollectedEntry


@dataclass
class ClassificationResult:
    """分類結果"""

    primary_category: Category
    confidence: float  # 0.0-1.0
    matched_keywords: list[str] = field(default_factory=list)
    category_scores: dict[str, float] = field(default_factory=dict)
    is_ignored: bool = False  # 無視キーワードにマッチした場合


class CategoryClassifier:
    """キーワードベースのカテゴリ分類器"""

    def __init__(self, keywords_path: Optional[Path] = None):
        """
        Args:
            keywords_path: keywords.yaml のパス（省略時はデフォルト）
        """
        if keywords_path is None:
            keywords_path = Path(__file__).parent.parent / "sources" / "keywords.yaml"

        self.keywords_path = keywords_path
        self._load_keywords()

    def _load_keywords(self) -> None:
        """キーワード定義を読み込み"""
        if not self.keywords_path.exists():
            raise FileNotFoundError(f"Keywords file not found: {self.keywords_path}")

        with open(self.keywords_path) as f:
            data = yaml.safe_load(f)

        # カテゴリ別キーワードを展開
        self.category_keywords: dict[Category, list[str]] = {}
        self.category_weights: dict[Category, float] = {}

        categories_data = data.get("categories", {})

        for cat_name, cat_data in categories_data.items():
            try:
                category = Category(cat_name)
            except ValueError:
                continue

            # 優先度をウェイトに変換
            priority = cat_data.get("priority", "medium")
            self.category_weights[category] = {
                "high": 1.5,
                "medium": 1.0,
                "low": 0.5,
            }.get(priority, 1.0)

            # サブカテゴリからキーワードを収集
            keywords = []
            for key, value in cat_data.items():
                if isinstance(value, list):
                    keywords.extend(value)

            self.category_keywords[category] = [kw.lower() for kw in keywords]

        # 無視キーワード
        ignore_data = data.get("ignore", {})
        self.ignore_keywords = [kw.lower() for kw in ignore_data.get("keywords", [])]

    def _normalize_text(self, text: str) -> str:
        """テキストを正規化"""
        # 小文字化
        text = text.lower()
        # ハイフン・アンダースコアをスペースに
        text = re.sub(r"[-_]", " ", text)
        # 複数スペースを単一に
        text = re.sub(r"\s+", " ", text)
        return text

    def _count_keyword_matches(self, text: str, keywords: list[str]) -> tuple[int, list[str]]:
        """キーワードマッチ数と該当キーワードを返す"""
        text = self._normalize_text(text)
        matched = []

        for kw in keywords:
            # キーワードが複数単語の場合はフレーズマッチ
            if " " in kw:
                if kw in text:
                    matched.append(kw)
            else:
                # 単語境界でマッチ
                pattern = rf"\b{re.escape(kw)}\b"
                if re.search(pattern, text):
                    matched.append(kw)

        return len(matched), matched

    def classify(self, entry: CollectedEntry) -> ClassificationResult:
        """エントリを分類

        Args:
            entry: 分類対象のエントリ

        Returns:
            分類結果
        """
        # 分類対象テキスト（タイトル + サマリ + 生コンテンツ）
        text = f"{entry.title} {entry.summary} {entry.raw_content}"

        # 無視キーワードチェック
        ignore_count, ignore_matched = self._count_keyword_matches(text, self.ignore_keywords)
        if ignore_count >= 2:  # 2つ以上マッチで無視
            return ClassificationResult(
                primary_category=Category.OTHER,
                confidence=0.0,
                matched_keywords=ignore_matched,
                category_scores={},
                is_ignored=True,
            )

        # カテゴリ別スコア計算
        category_scores: dict[Category, float] = {}
        all_matched: list[str] = []

        for category, keywords in self.category_keywords.items():
            count, matched = self._count_keyword_matches(text, keywords)
            if count > 0:
                # ウェイト適用
                weight = self.category_weights.get(category, 1.0)
                score = count * weight
                category_scores[category] = score
                all_matched.extend(matched)

        # スコアがない場合は OTHER
        if not category_scores:
            return ClassificationResult(
                primary_category=Category.OTHER,
                confidence=0.1,
                matched_keywords=[],
                category_scores={cat.value: 0.0 for cat in Category},
            )

        # 最高スコアのカテゴリを選択
        primary = max(category_scores, key=lambda c: category_scores[c])
        max_score = category_scores[primary]
        total_score = sum(category_scores.values())

        # 信頼度計算（最高スコアの割合 + マッチ数ボーナス）
        confidence = min(1.0, (max_score / total_score) * min(1.0, max_score / 3))

        return ClassificationResult(
            primary_category=primary,
            confidence=confidence,
            matched_keywords=list(set(all_matched)),
            category_scores={cat.value: category_scores.get(cat, 0.0) for cat in Category},
            is_ignored=False,
        )

    def classify_batch(self, entries: list[CollectedEntry]) -> list[ClassificationResult]:
        """複数エントリを一括分類"""
        return [self.classify(entry) for entry in entries]


if __name__ == "__main__":
    # テスト
    from collectors.models import SourceType

    classifier = CategoryClassifier()

    test_entries = [
        CollectedEntry(
            title="OpenAI releases GPT-5 with extended context",
            url="https://example.com/1",
            source_name="Test",
            source_type=SourceType.RSS,
            summary="New GPT-5 model with 1M token context window",
        ),
        CollectedEntry(
            title="Claude 4 pricing reduced by 50%",
            url="https://example.com/2",
            source_name="Test",
            source_type=SourceType.RSS,
            summary="Anthropic announces price reduction for Claude 4",
        ),
        CollectedEntry(
            title="Rate limit increase for API users",
            url="https://example.com/3",
            source_name="Test",
            source_type=SourceType.RSS,
            summary="New tier with higher RPM quota",
        ),
        CollectedEntry(
            title="Best practices tutorial for beginners",
            url="https://example.com/4",
            source_name="Test",
            source_type=SourceType.RSS,
            summary="Getting started guide with comparison",
        ),
    ]

    print("=== Category Classifier Test ===\n")

    for entry in test_entries:
        result = classifier.classify(entry)
        print(f"Title: {entry.title}")
        print(f"  Category: {result.primary_category.value}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Ignored: {result.is_ignored}")
        print(f"  Keywords: {', '.join(result.matched_keywords[:5])}")
        print()
