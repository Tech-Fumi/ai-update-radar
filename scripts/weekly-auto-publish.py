#!/usr/bin/env python3
"""
AI Update Radar - 週次自動公開スクリプト

完全自動化フロー:
1. collect (データ収集)
2. evaluate (評価)
3. generate-public-digest (公開用生成)
4. 判定: 通常週 → 自動投稿 / 要確認週 → 通知のみ

使用例:
    python3 scripts/weekly-auto-publish.py
    python3 scripts/weekly-auto-publish.py --dry-run
    python3 scripts/weekly-auto-publish.py --force-review
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests
import yaml

# パス設定
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
EXPORTS_DIR = PROJECT_ROOT / "exports"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "weekly"
DRAFTS_DIR = PROJECT_ROOT / "drafts"


def load_env():
    """プロジェクトルートの .env を読み込み"""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if key and value:
                        os.environ.setdefault(key, value)


# .env 読み込み（cron 実行時にも対応）
load_env()

# Discord Webhook（環境変数から取得）
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_ALERT_WEBHOOK_URL", "")


def get_current_week() -> str:
    """現在の週番号を取得（ISO形式）"""
    now = datetime.now()
    return now.strftime("%Y-W%V")


def get_latest_week() -> str | None:
    """最新の digest ファイルから週番号を取得"""
    digests = sorted(EXPORTS_DIR.glob("digest-*.json"), reverse=True)
    if not digests:
        return None
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


def check_needs_review(digest: dict, alerts: list) -> tuple[bool, list[str]]:
    """
    人間レビューが必要かどうかを判定

    Returns:
        (needs_review: bool, reasons: list[str])
    """
    reasons = []

    summary = digest.get("summary", {})
    layer3_count = summary.get("layer_3_count", 0)

    # Layer3 が 1 件以上 → 要確認
    if layer3_count > 0:
        reasons.append(f"Layer3（要深掘り）が {layer3_count} 件あります")

    # security/breaking アラートがある → 要確認
    critical_alerts = [a for a in alerts if a.get("type") in ("security", "breaking")]
    if critical_alerts:
        titles = [a.get("title", "不明")[:30] for a in critical_alerts[:3]]
        reasons.append(f"重要アラート: {', '.join(titles)}")

    return len(reasons) > 0, reasons


def send_discord_notification(message: str, urgent: bool = False):
    """Discord に通知を送信"""
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ DISCORD_ALERT_WEBHOOK_URL が設定されていません")
        return False

    color = 0xFF6600 if urgent else 0x00AA00  # オレンジ or 緑

    payload = {
        "embeds": [{
            "title": "🛰 AI Update Radar",
            "description": message,
            "color": color,
            "timestamp": datetime.utcnow().isoformat()
        }]
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Discord 通知失敗: {e}")
        return False


def save_as_draft(week: str):
    """下書きとして保存"""
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    # 生成済みファイルを drafts/ にコピー
    for fmt in ["blog", "note", "x"]:
        ext = "txt" if fmt == "x" else "md"
        src = OUTPUT_DIR / f"public-{week}-{fmt}.{ext}"
        dst = DRAFTS_DIR / f"draft-{week}-{fmt}.{ext}"

        if src.exists():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"📝 下書き保存: {DRAFTS_DIR}/")


def run_generate_digest(week: str) -> bool:
    """公開用ダイジェストを生成"""
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "generate-public-digest.py"),
        "--week", week
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ generate-public-digest 失敗:\n{result.stderr}")
        return False

    print(result.stdout)
    return True


def get_x_content(week: str) -> str:
    """X投稿用コンテンツを取得"""
    path = OUTPUT_DIR / f"public-{week}-x.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="週次自動公開")
    parser.add_argument("--week", help="対象週（例: 2025-W51）")
    parser.add_argument("--dry-run", action="store_true", help="実行せずに確認のみ")
    parser.add_argument("--force-review", action="store_true", help="強制的にレビューモード")
    parser.add_argument("--skip-generate", action="store_true", help="生成をスキップ")
    args = parser.parse_args()

    # 週の決定
    week = args.week or get_latest_week()
    if not week:
        print("❌ 対象週が見つかりません")
        return 1

    print(f"{'=' * 50}")
    print(f"🛰 AI Update Radar 週次自動公開")
    print(f"📅 対象週: {week}")
    print(f"{'=' * 50}")
    print()

    # 1. 公開用ダイジェスト生成
    if not args.skip_generate:
        print("📝 ダイジェスト生成中...")
        if not run_generate_digest(week):
            return 1
        print()

    # 2. データ読み込み
    digest = load_digest(week)
    alerts = load_alerts(week)

    if not digest:
        print(f"❌ digest-{week}.json が見つかりません")
        return 1

    # 3. レビュー必要性の判定
    needs_review, reasons = check_needs_review(digest, alerts)

    if args.force_review:
        needs_review = True
        reasons.append("--force-review が指定されました")

    # 4. 結果に応じた処理
    summary = digest.get("summary", {})
    total = summary.get("total_evaluated", 0)
    layer3 = summary.get("layer_3_count", 0)

    x_content = get_x_content(week)

    if needs_review:
        # === 要確認モード ===
        print("🟡 要確認週です（自動投稿スキップ）")
        print()
        print("理由:")
        for r in reasons:
            print(f"  - {r}")
        print()

        if not args.dry_run:
            # 下書き保存
            save_as_draft(week)

            # Discord 通知
            message = f"""**週次レポート確認依頼**

📅 **{week}**
📊 評価: {total}件 / Layer3: {layer3}件

⚠️ **確認が必要な理由:**
{chr(10).join('• ' + r for r in reasons)}

👉 `drafts/` フォルダを確認して、問題なければ手動投稿してください。"""

            send_discord_notification(message, urgent=True)
            print()
            print("📨 Discord に通知しました")

    else:
        # === 通常週（自動投稿OK）===
        print("🟢 通常週です（自動投稿可能）")
        print()
        print("X 投稿内容:")
        print("-" * 40)
        print(x_content)
        print("-" * 40)
        print()

        if args.dry_run:
            print("🔍 dry-run モード: 投稿はスキップ")
        else:
            # TODO: X API 自動投稿（将来実装）
            # 現時点では通知のみ
            message = f"""**週次レポート準備完了**

📅 **{week}**
📊 評価: {total}件（静かな週）

✅ 自動投稿可能な週です。

**X投稿内容:**
```
{x_content}
```

👉 `docs/weekly/public-{week}-x.txt` をコピペで投稿してください。"""

            send_discord_notification(message, urgent=False)
            print("📨 Discord に通知しました（投稿準備完了）")

    print()
    print("✅ 完了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
