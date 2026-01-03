"""
トレンド検知モジュール

キーワード頻度の変化からトレンドを検出
"""

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import yaml


class TrendDetector:
    """キーワード監視とトレンド検知"""

    def __init__(
        self,
        data_dir: Path,
        output_dir: Path,
        threshold_ratio: float = 1.5,
    ):
        """
        Args:
            data_dir: 収集データディレクトリ（.private/marketing/）
            output_dir: トレンド出力先（.private/marketing/trends/）
            threshold_ratio: トレンド判定閾値（前週比）
        """
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.threshold_ratio = threshold_ratio

    def _load_entries_for_period(
        self, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        """
        指定期間のエントリを読み込み

        Args:
            start_date: 開始日
            end_date: 終了日

        Returns:
            list[dict]: エントリリスト
        """
        entries = []

        # competitors ディレクトリからファイルを読み込み
        competitors_dir = self.data_dir / "competitors"
        if competitors_dir.exists():
            for json_file in competitors_dir.glob("competitor-*.json"):
                # ファイル名から日付を抽出
                date_str = json_file.stem.replace("competitor-", "")
                try:
                    file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                    if start_date <= file_date <= end_date:
                        with open(json_file, encoding="utf-8") as f:
                            data = json.load(f)
                            for result in data.get("results", []):
                                entries.extend(result.get("entries", []))
                except (ValueError, json.JSONDecodeError):
                    continue

        return entries

    def _extract_keywords(self, entries: list[dict]) -> Counter:
        """
        エントリからキーワードを抽出してカウント

        Args:
            entries: エントリリスト

        Returns:
            Counter: キーワード出現回数
        """
        keywords = []
        for entry in entries:
            # 明示的なキーワード
            keywords.extend(entry.get("keywords", []))

            # タイトルから重要語を抽出（簡易版）
            title = entry.get("title", "")
            # AI関連キーワードをチェック
            ai_keywords = [
                "AI",
                "LLM",
                "GPT",
                "Claude",
                "Agent",
                "MCP",
                "RAG",
                "embedding",
                "fine-tuning",
                "prompt",
                "automation",
            ]
            for kw in ai_keywords:
                if kw.lower() in title.lower():
                    keywords.append(kw)

        return Counter(keywords)

    def detect_trends(
        self,
        current_week_start: Optional[datetime] = None,
    ) -> dict:
        """
        トレンドを検出

        Args:
            current_week_start: 今週の開始日（デフォルト: 今日から7日前）

        Returns:
            dict: トレンド分析結果
        """
        if current_week_start is None:
            current_week_start = datetime.now(timezone.utc) - timedelta(days=7)

        current_week_end = current_week_start + timedelta(days=7)
        prev_week_start = current_week_start - timedelta(days=7)
        prev_week_end = current_week_start

        # 各期間のエントリを取得
        current_entries = self._load_entries_for_period(
            current_week_start, current_week_end
        )
        prev_entries = self._load_entries_for_period(prev_week_start, prev_week_end)

        # キーワードカウント
        current_counts = self._extract_keywords(current_entries)
        prev_counts = self._extract_keywords(prev_entries)

        # トレンド判定
        rising_trends = []
        declining_trends = []
        stable_trends = []

        all_keywords = set(current_counts.keys()) | set(prev_counts.keys())

        for keyword in all_keywords:
            current_count = current_counts.get(keyword, 0)
            prev_count = prev_counts.get(keyword, 0)

            if prev_count == 0:
                if current_count >= 2:
                    # 新規出現
                    rising_trends.append(
                        {
                            "keyword": keyword,
                            "current_count": current_count,
                            "prev_count": prev_count,
                            "change": "new",
                            "ratio": float("inf"),
                        }
                    )
            else:
                ratio = current_count / prev_count
                trend_data = {
                    "keyword": keyword,
                    "current_count": current_count,
                    "prev_count": prev_count,
                    "ratio": round(ratio, 2),
                }

                if ratio >= self.threshold_ratio:
                    trend_data["change"] = "rising"
                    rising_trends.append(trend_data)
                elif ratio <= 1 / self.threshold_ratio:
                    trend_data["change"] = "declining"
                    declining_trends.append(trend_data)
                else:
                    trend_data["change"] = "stable"
                    stable_trends.append(trend_data)

        # スコア順でソート
        rising_trends.sort(
            key=lambda x: (x["ratio"] if x["ratio"] != float("inf") else 999),
            reverse=True,
        )
        declining_trends.sort(key=lambda x: x["ratio"])

        result = {
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "period": {
                "current": {
                    "start": current_week_start.isoformat(),
                    "end": current_week_end.isoformat(),
                    "entries_count": len(current_entries),
                },
                "previous": {
                    "start": prev_week_start.isoformat(),
                    "end": prev_week_end.isoformat(),
                    "entries_count": len(prev_entries),
                },
            },
            "trends": {
                "rising": rising_trends[:10],  # 上位10件
                "declining": declining_trends[:10],
                "stable_count": len(stable_trends),
            },
            "summary": {
                "total_keywords": len(all_keywords),
                "rising_count": len(rising_trends),
                "declining_count": len(declining_trends),
            },
        }

        return result

    def save_trends(self, trends: dict) -> Path:
        """
        トレンド結果を保存

        Args:
            trends: トレンド分析結果

        Returns:
            Path: 保存先パス
        """
        now = datetime.now(timezone.utc)
        week_num = now.strftime("%Y-W%V")
        filename = f"trends-{week_num}.json"
        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(trends, f, indent=2, ensure_ascii=False)

        return output_path

    def get_alerts(self, trends: dict) -> list[dict]:
        """
        トレンドからアラートを生成

        Args:
            trends: トレンド分析結果

        Returns:
            list[dict]: アラートリスト
        """
        alerts = []

        # 急上昇キーワードをアラート
        for trend in trends.get("trends", {}).get("rising", [])[:5]:
            if trend.get("change") == "new":
                alerts.append(
                    {
                        "type": "trend_new",
                        "title": f"新トレンド検出: {trend['keyword']}",
                        "description": f"今週新たに {trend['current_count']} 回出現",
                        "keyword": trend["keyword"],
                        "priority": "high",
                    }
                )
            else:
                alerts.append(
                    {
                        "type": "trend_rising",
                        "title": f"トレンド上昇: {trend['keyword']}",
                        "description": f"前週比 {trend['ratio']}倍 ({trend['prev_count']} → {trend['current_count']})",
                        "keyword": trend["keyword"],
                        "priority": "medium",
                    }
                )

        return alerts
