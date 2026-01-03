"""
SNS投稿候補生成モジュール

トレンド・アラートからSNS投稿候補を自動生成
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class ContentGenerator:
    """
    SNS投稿候補を自動生成

    トレンド検出結果・週次ダイジェスト・アラートから
    プラットフォーム別の投稿候補を生成する
    """

    # X (Twitter) の文字数制限
    X_CHAR_LIMIT = 280

    # 投稿テンプレート
    TEMPLATES = {
        "trend_new": """🔥 新トレンド検出

{keyword} が今週急浮上

{context}

#AI週報 #LLM""",
        "trend_rising": """📈 トレンド上昇中

{keyword}: 前週比 {ratio}倍

{context}

#AI週報 #トレンド""",
        "weekly_digest": """🛰 AI Update Radar {week}

{summary}

{highlights}

#AI週報 #LLM""",
        "opportunity": """💡 ビジネス機会

{title}

{insight}

#AI運用 #ビジネス""",
        "alert": """⚠️ {alert_type}

{title}

{description}

#AI #速報""",
    }

    def __init__(self, output_dir: Path):
        """
        Args:
            output_dir: 出力先ディレクトリ
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _truncate_for_x(self, text: str, reserve: int = 30) -> str:
        """
        X向けに文字数を調整

        Args:
            text: 元テキスト
            reserve: ハッシュタグ等の予約文字数

        Returns:
            str: 調整後テキスト
        """
        limit = self.X_CHAR_LIMIT - reserve
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    def generate_from_trends(self, trends: dict) -> list[dict]:
        """
        トレンドデータから投稿候補を生成

        Args:
            trends: TrendDetector の出力

        Returns:
            list[dict]: 投稿候補リスト
        """
        candidates = []
        rising = trends.get("trends", {}).get("rising", [])

        for trend in rising[:3]:  # 上位3件
            keyword = trend.get("keyword", "")
            ratio = trend.get("ratio", 0)
            change = trend.get("change", "")

            if change == "new":
                template = self.TEMPLATES["trend_new"]
                context = f"今週 {trend.get('current_count', 0)} 回出現"
            else:
                template = self.TEMPLATES["trend_rising"]
                context = f"{trend.get('prev_count', 0)} → {trend.get('current_count', 0)}"

            content = template.format(
                keyword=keyword,
                ratio=ratio if ratio != float("inf") else "∞",
                context=context,
            )

            # X向けに調整
            x_content = self._truncate_for_x(content)

            candidates.append(
                {
                    "type": "trend",
                    "platform": "x",
                    "content": x_content,
                    "full_content": content,
                    "source_data": trend,
                    "priority": "high" if change == "new" else "medium",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        return candidates

    def generate_from_digest(
        self,
        week: str,
        digest: dict,
        alerts: Optional[list] = None,
    ) -> list[dict]:
        """
        週次ダイジェストから投稿候補を生成

        Args:
            week: 週番号（YYYY-WXX）
            digest: digest JSON
            alerts: アラートリスト

        Returns:
            list[dict]: 投稿候補リスト
        """
        candidates = []
        summary = digest.get("summary", {})

        # メインダイジェスト投稿
        total = summary.get("total_evaluated", 0)
        layer3 = summary.get("layer_3_count", 0)

        if layer3 > 0:
            summary_text = f"📊 {total}件評価 → {layer3}件が要深掘り（荒れ週）"
        else:
            summary_text = f"📊 {total}件評価（静かな週）"

        highlights = digest.get("highlights", [])
        highlights_text = ""
        if highlights:
            highlights_text = "\n".join([f"• {h[:30]}..." for h in highlights[:2]])

        content = self.TEMPLATES["weekly_digest"].format(
            week=week,
            summary=summary_text,
            highlights=highlights_text,
        )

        x_content = self._truncate_for_x(content)

        candidates.append(
            {
                "type": "weekly_digest",
                "platform": "x",
                "content": x_content,
                "full_content": content,
                "source_data": {"week": week, "summary": summary},
                "priority": "high",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # 重要アラートがあれば個別投稿候補も生成
        if alerts:
            critical_alerts = [
                a for a in alerts if a.get("type") in ("security", "breaking")
            ]
            for alert in critical_alerts[:2]:
                alert_content = self.TEMPLATES["alert"].format(
                    alert_type="重要アップデート",
                    title=alert.get("title", "")[:50],
                    description=alert.get("description", "")[:100],
                )

                candidates.append(
                    {
                        "type": "alert",
                        "platform": "x",
                        "content": self._truncate_for_x(alert_content),
                        "full_content": alert_content,
                        "source_data": alert,
                        "priority": "high",
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

        return candidates

    def generate_from_opportunities(self, entries: list[dict]) -> list[dict]:
        """
        ビジネス機会エントリから投稿候補を生成

        Args:
            entries: 競合分析のopportunities結果

        Returns:
            list[dict]: 投稿候補リスト
        """
        candidates = []

        for entry in entries[:3]:
            title = entry.get("title", "")[:50]
            summary = entry.get("summary", "")[:100]

            content = self.TEMPLATES["opportunity"].format(
                title=title,
                insight=summary,
            )

            candidates.append(
                {
                    "type": "opportunity",
                    "platform": "x",
                    "content": self._truncate_for_x(content),
                    "full_content": content,
                    "source_data": entry,
                    "priority": "low",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        return candidates

    def save_candidates(self, candidates: list[dict], week: str) -> Path:
        """
        投稿候補を保存

        Args:
            candidates: 投稿候補リスト
            week: 週番号

        Returns:
            Path: 保存先パス
        """
        filename = f"content-candidates-{week}.json"
        output_path = self.output_dir / filename

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "week": week,
            "candidates_count": len(candidates),
            "candidates": candidates,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path

    def get_ready_to_post(self, week: str) -> list[dict]:
        """
        投稿準備が完了した候補を取得

        Args:
            week: 週番号

        Returns:
            list[dict]: 投稿準備完了の候補（優先度順）
        """
        filename = f"content-candidates-{week}.json"
        file_path = self.output_dir / filename

        if not file_path.exists():
            return []

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        candidates = data.get("candidates", [])

        # 優先度でソート
        priority_order = {"high": 0, "medium": 1, "low": 2}
        candidates.sort(key=lambda c: priority_order.get(c.get("priority", "low"), 2))

        return candidates
