# AI Update Radar - Collectors
"""
監視対象から情報を自動収集するスクリプト群
"""

from collectors.models import Category, CollectedEntry, CollectionResult, SourceType

try:
    from collectors.news_crosscheck import NewsCrosscheckCollector
except ModuleNotFoundError:  # pragma: no cover - optional dependency missing in minimal env
    NewsCrosscheckCollector = None

try:
    from collectors.github_collector import GitHubCollector
except ModuleNotFoundError:  # pragma: no cover - optional dependency missing in minimal env
    GitHubCollector = None

try:
    from collectors.page_diff_collector import PageDiffCollector
except ModuleNotFoundError:  # pragma: no cover - optional dependency missing in minimal env
    PageDiffCollector = None

try:
    from collectors.rss_collector import RSSCollector
except ModuleNotFoundError:  # pragma: no cover - optional dependency missing in minimal env
    RSSCollector = None

__all__ = [
    "Category",
    "CollectedEntry",
    "CollectionResult",
    "SourceType",
    "RSSCollector",
    "GitHubCollector",
    "PageDiffCollector",
    "NewsCrosscheckCollector",
]
