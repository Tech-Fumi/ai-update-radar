"""
効果測定連携モジュール

公開コンテンツのパフォーマンスを追跡
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class AnalyticsTracker:
    """
    公開コンテンツの効果測定

    X Analytics / Note / ブログ等の外部ツールと連携し、
    投稿パフォーマンスを追跡する
    """

    def __init__(self, data_dir: Path):
        """
        Args:
            data_dir: データ保存先（.private/marketing/analytics/）
        """
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_data_path(self) -> Path:
        """データファイルのパス"""
        return self.data_dir / "performance.json"

    def _load_data(self) -> dict:
        """パフォーマンスデータを読み込み"""
        data_path = self._get_data_path()
        if data_path.exists():
            with open(data_path, encoding="utf-8") as f:
                return json.load(f)
        return {"posts": [], "summary": {}}

    def _save_data(self, data: dict) -> None:
        """パフォーマンスデータを保存"""
        data_path = self._get_data_path()
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def record_post(
        self,
        platform: str,
        post_id: str,
        content_type: str,
        week: str,
        url: Optional[str] = None,
        published_at: Optional[datetime] = None,
    ) -> dict:
        """
        投稿を記録

        Args:
            platform: プラットフォーム（x, note, blog）
            post_id: 投稿ID
            content_type: コンテンツタイプ（weekly_digest, trend_alert等）
            week: 対象週（YYYY-WXX）
            url: 投稿URL
            published_at: 投稿日時

        Returns:
            dict: 記録した投稿データ
        """
        data = self._load_data()

        post = {
            "id": f"{platform}-{post_id}",
            "platform": platform,
            "post_id": post_id,
            "content_type": content_type,
            "week": week,
            "url": url,
            "published_at": (published_at or datetime.now(timezone.utc)).isoformat(),
            "metrics": {},
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        # 既存の同じ投稿を更新するか、新規追加
        existing_idx = next(
            (i for i, p in enumerate(data["posts"]) if p["id"] == post["id"]),
            None,
        )
        if existing_idx is not None:
            data["posts"][existing_idx].update(post)
        else:
            data["posts"].append(post)

        self._save_data(data)
        return post

    def update_metrics(
        self,
        platform: str,
        post_id: str,
        impressions: Optional[int] = None,
        engagements: Optional[int] = None,
        clicks: Optional[int] = None,
        likes: Optional[int] = None,
        retweets: Optional[int] = None,
        replies: Optional[int] = None,
        **kwargs,
    ) -> Optional[dict]:
        """
        投稿のメトリクスを更新

        Args:
            platform: プラットフォーム
            post_id: 投稿ID
            impressions: インプレッション数
            engagements: エンゲージメント数
            clicks: クリック数
            likes: いいね数
            retweets: リツイート数
            replies: リプライ数
            **kwargs: その他のメトリクス

        Returns:
            dict: 更新後の投稿データ（見つからない場合はNone）
        """
        data = self._load_data()
        target_id = f"{platform}-{post_id}"

        for post in data["posts"]:
            if post["id"] == target_id:
                metrics = post.get("metrics", {})

                if impressions is not None:
                    metrics["impressions"] = impressions
                if engagements is not None:
                    metrics["engagements"] = engagements
                if clicks is not None:
                    metrics["clicks"] = clicks
                if likes is not None:
                    metrics["likes"] = likes
                if retweets is not None:
                    metrics["retweets"] = retweets
                if replies is not None:
                    metrics["replies"] = replies

                # その他のメトリクス
                for key, value in kwargs.items():
                    metrics[key] = value

                post["metrics"] = metrics
                post["last_updated"] = datetime.now(timezone.utc).isoformat()

                self._save_data(data)
                return post

        return None

    def get_performance_summary(
        self,
        platform: Optional[str] = None,
        weeks: int = 4,
    ) -> dict:
        """
        パフォーマンスサマリを取得

        Args:
            platform: プラットフォームでフィルタ（None=全て）
            weeks: 対象週数

        Returns:
            dict: サマリデータ
        """
        data = self._load_data()
        posts = data.get("posts", [])

        if platform:
            posts = [p for p in posts if p["platform"] == platform]

        # 最新 N 週分のみ
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)
        recent_posts = []
        for post in posts:
            try:
                pub_date = datetime.fromisoformat(post["published_at"])
                if pub_date >= cutoff:
                    recent_posts.append(post)
            except (ValueError, KeyError):
                continue

        # 集計
        total_impressions = 0
        total_engagements = 0
        total_clicks = 0

        for post in recent_posts:
            metrics = post.get("metrics", {})
            total_impressions += metrics.get("impressions", 0)
            total_engagements += metrics.get("engagements", 0)
            total_clicks += metrics.get("clicks", 0)

        engagement_rate = (
            (total_engagements / total_impressions * 100)
            if total_impressions > 0
            else 0
        )
        click_rate = (
            (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        )

        return {
            "period_weeks": weeks,
            "platform": platform or "all",
            "posts_count": len(recent_posts),
            "total_impressions": total_impressions,
            "total_engagements": total_engagements,
            "total_clicks": total_clicks,
            "engagement_rate": round(engagement_rate, 2),
            "click_rate": round(click_rate, 2),
            "top_posts": sorted(
                recent_posts,
                key=lambda p: p.get("metrics", {}).get("engagements", 0),
                reverse=True,
            )[:5],
        }

    def get_content_type_performance(self) -> dict:
        """
        コンテンツタイプ別パフォーマンスを取得

        Returns:
            dict: タイプ別サマリ
        """
        data = self._load_data()
        posts = data.get("posts", [])

        type_stats = {}
        for post in posts:
            content_type = post.get("content_type", "unknown")
            if content_type not in type_stats:
                type_stats[content_type] = {
                    "count": 0,
                    "total_impressions": 0,
                    "total_engagements": 0,
                }

            stats = type_stats[content_type]
            stats["count"] += 1
            metrics = post.get("metrics", {})
            stats["total_impressions"] += metrics.get("impressions", 0)
            stats["total_engagements"] += metrics.get("engagements", 0)

        # 平均を計算
        for content_type, stats in type_stats.items():
            if stats["count"] > 0:
                stats["avg_impressions"] = round(
                    stats["total_impressions"] / stats["count"]
                )
                stats["avg_engagements"] = round(
                    stats["total_engagements"] / stats["count"]
                )

        return type_stats
