#!/usr/bin/env python3
"""
AI Update Radar - 公開用ダイジェスト生成

exports/digest-*.json → docs/weekly/public-*.md
ブログ/Note/X 向けに自動整形

使用例:
    python3 scripts/generate-public-digest.py
    python3 scripts/generate-public-digest.py --week 2025-W51
    python3 scripts/generate-public-digest.py --format x  # X向け短縮版
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import yaml

# パス設定
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
EXPORTS_DIR = PROJECT_ROOT / "exports"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "weekly"


def get_latest_week() -> str | None:
    """最新の digest ファイルから週番号を取得"""
    digests = sorted(EXPORTS_DIR.glob("digest-*.json"), reverse=True)
    if not digests:
        return None
    # digest-2025-W51.json → 2025-W51
    return digests[0].stem.replace("digest-", "")


def load_digest(week: str) -> dict:
    """digest JSON を読み込み"""
    path = EXPORTS_DIR / f"digest-{week}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_alerts(week: str) -> list[dict]:
    """alerts YAML を読み込み（重複排除済み）"""
    path = EXPORTS_DIR / f"alerts-{week}.yaml"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
        raw_alerts = data.get("alerts", []) if data else []

    # URL とタイトルで重複排除
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique_alerts = []
    for alert in raw_alerts:
        url = alert.get("url", "")
        title = alert.get("title", "")

        # URL または タイトル が既出ならスキップ
        if url and url in seen_urls:
            continue
        if title and title in seen_titles:
            continue

        if url:
            seen_urls.add(url)
        if title:
            seen_titles.add(title)
        unique_alerts.append(alert)

    return unique_alerts


def load_adopted(week: str) -> list[dict]:
    """adopted YAML を読み込み"""
    path = EXPORTS_DIR / f"adopted-{week}.yaml"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data.get("adopted", []) if data else []


def format_blog_digest(week: str, digest: dict, alerts: list, adopted: list) -> str:
    """ブログ/Note 向けフルバージョン"""
    summary = digest.get("summary", {})
    total = summary.get("total_evaluated", 0)
    layer3 = summary.get("layer_3_count", 0)
    layer2 = summary.get("layer_2_count", 0)

    lines = [
        f"# 🛰 AI Update Radar - {week}",
        "",
        f"> 今週の AI 界隈の動向サマリ（{total}件を評価）",
        "",
        "---",
        "",
        "## 📊 今週の数字",
        "",
        f"- **評価した更新**: {total}件",
        f"- **要注目（Layer3）**: {layer3}件",
        f"- **記録のみ（Layer2）**: {layer2}件",
        "",
    ]

    # リリース/更新情報（security/breaking → 「リリース」として扱う）
    important_alerts = [a for a in alerts if a.get("type") in ("security", "breaking")]
    notice_alerts = [a for a in alerts if a.get("type") == "notice"]

    if important_alerts:
        lines.append("## 📢 注目リリース")
        lines.append("")
        for alert in important_alerts[:3]:  # 最大3件
            title = alert.get("title", "")
            url = alert.get("url", "")
            lines.append(f"- **{title}**")
            if url:
                lines.append(f"  - {url}")
        lines.append("")

    if notice_alerts:
        lines.append("## 📝 その他の更新")
        lines.append("")
        for alert in notice_alerts[:5]:  # 最大5件
            title = alert.get("title", "")
            lines.append(f"- {title}")
        lines.append("")

    # 採用候補
    if adopted:
        lines.append("## ✅ 採用候補")
        lines.append("")
        for item in adopted[:3]:
            name = item.get("name", "unknown")
            lines.append(f"- {name}")
        lines.append("")

    # PoC
    highlights = digest.get("highlights", [])
    if highlights:
        lines.append("## 🧪 PoC 進行中")
        lines.append("")
        for h in highlights[:3]:
            lines.append(f"- {h}")
        lines.append("")

    # フッター
    lines.append("---")
    lines.append("")

    # 導線（収益化の入口）
    lines.append("## 📬 AI運用についてのご相談")
    lines.append("")
    lines.append("AI更新を追うのではなく、**採用判断まで含めた運用設計**をサポートします。")
    lines.append("")
    lines.append("- 週次ダイジェスト生成の仕組み構築")
    lines.append("- 採用ルール・評価基準の策定")
    lines.append("- PoC テンプレート・実験環境の設計")
    lines.append("")
    lines.append("ご相談は **X（@Tech_Fumi1）の DM** へ")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated by AI Update Radar - {datetime.now().strftime('%Y-%m-%d')}*")

    return "\n".join(lines)


def format_x_digest(week: str, digest: dict, alerts: list, adopted: list) -> str:
    """
    X (Twitter) 向け短縮版（280字以内目標）

    伸びる型:
    1. 今週の温度感（静/荒）
    2. 重要トピック1つ（名詞を出す）
    3. 自分の判断（採用/見送り/観測）
    4. 次のアクション（PoCするなら宣言）
    5. ハッシュタグは2つまで
    """
    summary = digest.get("summary", {})
    total = summary.get("total_evaluated", 0)
    layer3 = summary.get("layer_3_count", 0)
    highlights = digest.get("highlights", [])

    # 注目リリースを1つ取得（security → 「リリース」として扱う）
    important_alerts = [a for a in alerts if a.get("type") in ("security", "breaking")]
    top_release = important_alerts[0]["title"] if important_alerts else None

    parts = []

    # 1. 温度感
    if layer3 > 0:
        parts.append(f"🛰 AI Update Radar {week}：荒れ週")
        parts.append(f"📊 {total}件評価 → {layer3}件が要深掘り")
    else:
        parts.append(f"🛰 AI Update Radar {week}：静かな週")
        parts.append("→ 運用整備・検証に回すチャンス")

    # 2. 重要トピック（リリースとして表現）
    if top_release:
        short_title = top_release[:30] + "..." if len(top_release) > 30 else top_release
        parts.append(f"📢 注目リリース: {short_title}")

    # 3. 自分の判断
    if adopted:
        parts.append(f"✅ 今週の採用: {len(adopted)}件")
    elif layer3 > 0:
        parts.append("👀 観測中（採用判断は来週）")

    # 4. 次のアクション（PoC があれば）
    if highlights:
        parts.append(f"🧪 PoC進行中: {highlights[0][:20]}...")

    parts.append("")
    parts.append("#AI週報 #LLM")

    return "\n".join(parts)


def format_note_digest(week: str, digest: dict, alerts: list, adopted: list) -> str:
    """Note 向け（ブログと同じだが見出しを少し調整）"""
    # 基本はブログと同じ
    content = format_blog_digest(week, digest, alerts, adopted)
    # Note 向けの調整（絵文字多め、読みやすい改行）
    return content


def main():
    parser = argparse.ArgumentParser(description="公開用ダイジェスト生成")
    parser.add_argument("--week", help="対象週（例: 2025-W51）")
    parser.add_argument(
        "--format",
        choices=["blog", "note", "x", "all"],
        default="all",
        help="出力形式（default: all）",
    )
    parser.add_argument("--dry-run", action="store_true", help="ファイル出力せず表示のみ")
    args = parser.parse_args()

    # 週の決定
    week = args.week or get_latest_week()
    if not week:
        print("❌ exports に digest ファイルがありません")
        return 1

    print(f"📅 対象週: {week}")

    # データ読み込み
    digest = load_digest(week)
    alerts = load_alerts(week)
    adopted = load_adopted(week)

    if not digest:
        print(f"❌ digest-{week}.json が見つかりません")
        return 1

    print(f"  ✅ digest: {len(digest)} keys")
    print(f"  ✅ alerts: {len(alerts)} 件")
    print(f"  ✅ adopted: {len(adopted)} 件")
    print()

    # 出力ディレクトリ作成
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    formats_to_generate = ["blog", "note", "x"] if args.format == "all" else [args.format]

    for fmt in formats_to_generate:
        if fmt == "blog":
            content = format_blog_digest(week, digest, alerts, adopted)
            filename = f"public-{week}-blog.md"
        elif fmt == "note":
            content = format_note_digest(week, digest, alerts, adopted)
            filename = f"public-{week}-note.md"
        elif fmt == "x":
            content = format_x_digest(week, digest, alerts, adopted)
            filename = f"public-{week}-x.txt"

        if args.dry_run:
            print(f"=== {fmt.upper()} ({filename}) ===")
            print(content)
            print()
        else:
            output_path = OUTPUT_DIR / filename
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ {fmt}: {output_path}")

    if not args.dry_run:
        print()
        print(f"📁 出力先: {OUTPUT_DIR}/")

    return 0


if __name__ == "__main__":
    exit(main())
