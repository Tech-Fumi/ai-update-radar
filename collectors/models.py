"""
共通データモデル
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Category(str, Enum):
    """変化のカテゴリ"""

    CAPABILITY = "capability"  # 能力変化
    CONSTRAINT = "constraint"  # 制限解除
    PRICING = "pricing"  # 価格変化
    OTHER = "other"  # その他


class SourceType(str, Enum):
    """ソースの種類"""

    RSS = "rss"
    GITHUB_RELEASE = "github_release"
    PAGE_DIFF = "page_diff"
    API = "api"
    WEB_SEARCH = "web_search"


@dataclass
class CollectedEntry:
    """収集されたエントリ"""

    title: str
    url: str
    source_name: str
    source_type: SourceType
    published_at: Optional[datetime] = None
    summary: str = ""
    categories: list[Category] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    raw_content: str = ""
    raw_data: Optional[dict] = None  # WebSearch 等の生データ保持用

    def to_dict(self) -> dict:
        """辞書に変換"""
        return {
            "title": self.title,
            "url": self.url,
            "source_name": self.source_name,
            "source_type": self.source_type.value,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "summary": self.summary,
            "categories": [c.value for c in self.categories],
            "keywords": self.keywords,
            "raw_content": self.raw_content,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CollectedEntry":
        """辞書から復元"""
        published_at = None
        if data.get("published_at"):
            published_at = datetime.fromisoformat(data["published_at"])

        categories = []
        for c in data.get("categories", []):
            try:
                categories.append(Category(c))
            except ValueError:
                pass

        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            source_name=data.get("source_name", ""),
            source_type=SourceType(data.get("source_type", "rss")),
            published_at=published_at,
            summary=data.get("summary", ""),
            categories=categories,
            keywords=data.get("keywords", []),
            raw_content=data.get("raw_content", ""),
        )


@dataclass
class CollectionResult:
    """収集結果"""

    source_name: str
    source_type: SourceType
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    entries: list[CollectedEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    success: bool = True

    def to_dict(self) -> dict:
        """辞書に変換"""
        return {
            "source_name": self.source_name,
            "source_type": self.source_type.value,
            "collected_at": self.collected_at.isoformat(),
            "entry_count": len(self.entries),
            "entries": [e.to_dict() for e in self.entries],
            "errors": self.errors,
            "success": self.success,
        }
