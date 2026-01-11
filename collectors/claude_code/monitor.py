#!/usr/bin/env python3
"""
Claude Code リリース監視スクリプト

GitHub Releases の Atom フィードを監視し、新しいリリースがあれば Discord に通知する。
"""

import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import feedparser
import requests

# 設定
FEED_URL = "https://github.com/anthropics/claude-code/releases.atom"
STATE_FILE = Path(__file__).parent / ".last_release_state.json"
DISCORD_WEBHOOK_URL = os.environ.get("CLAUDE_CODE_DISCORD_WEBHOOK")


def get_feed() -> list[dict]:
    """Atom フィードを取得してパース"""
    feed = feedparser.parse(FEED_URL)

    if feed.bozo:
        print(f"[ERROR] フィード取得エラー: {feed.bozo_exception}", file=sys.stderr)
        return []

    releases = []
    for entry in feed.entries[:10]:  # 最新10件
        releases.append({
            "id": entry.id,
            "title": entry.title,
            "link": entry.link,
            "updated": entry.updated,
            "summary": entry.summary[:500] if entry.summary else "",
        })

    return releases


def load_state() -> dict:
    """前回の状態を読み込み"""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_id": None, "last_check": None}


def save_state(state: dict) -> None:
    """状態を保存"""
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def send_discord_notification(release: dict) -> bool:
    """Discord に通知を送信"""
    if not DISCORD_WEBHOOK_URL:
        print("[WARN] CLAUDE_CODE_DISCORD_WEBHOOK が設定されていません", file=sys.stderr)
        return False

    # リリースノートから主要な変更点を抽出（HTML タグを簡易除去）
    import re
    summary = re.sub(r'<[^>]+>', '', release["summary"])
    summary = summary.strip()[:400]

    embed = {
        "title": f"🚀 {release['title']}",
        "url": release["link"],
        "description": summary if summary else "新しいリリースが公開されました",
        "color": 0x7C3AED,  # 紫色
        "timestamp": release["updated"],
        "footer": {
            "text": "Claude Code Release Monitor"
        },
        "fields": [
            {
                "name": "📎 リリースページ",
                "value": f"[GitHub で見る]({release['link']})",
                "inline": True
            },
            {
                "name": "📅 更新日時",
                "value": release["updated"][:10],
                "inline": True
            }
        ]
    }

    payload = {
        "embeds": [embed]
    }

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"[ERROR] Discord 通知失敗: {e}", file=sys.stderr)
        return False


def main():
    print(f"[{datetime.now().isoformat()}] Claude Code リリース監視開始")

    # フィード取得
    releases = get_feed()
    if not releases:
        print("[WARN] リリース情報を取得できませんでした")
        return

    latest = releases[0]
    print(f"[INFO] 最新リリース: {latest['title']}")

    # 前回の状態と比較
    state = load_state()

    if state["last_id"] == latest["id"]:
        print("[INFO] 新しいリリースはありません")
    else:
        print(f"[INFO] 新しいリリースを検出: {latest['title']}")

        # Discord 通知
        if send_discord_notification(latest):
            print("[INFO] Discord 通知送信完了")

        # 状態を更新
        state["last_id"] = latest["id"]

    state["last_check"] = datetime.now().isoformat()
    save_state(state)

    print(f"[{datetime.now().isoformat()}] 監視完了")


if __name__ == "__main__":
    main()
