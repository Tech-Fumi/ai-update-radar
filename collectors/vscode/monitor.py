#!/usr/bin/env python3
"""
VS Code 軽量監視
- GitHub releases を取得
- AI 関連の変更のみを抽出（キーワードフィルタ）
- 重要な変更（破壊的変更、セキュリティ）を検出
- vscode_releases.json に統合
"""

import json
import os
import requests
from datetime import datetime
from pathlib import Path

# .env から API キーを読み込み
env_file = Path.home() / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value.strip('"').strip("'")

import anthropic

GITHUB_REPO = "microsoft/vscode"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "data"

# AI 関連キーワード（リリースノートフィルタ用）
AI_RELEVANT_KEYWORDS = [
    "copilot", "ai", "artificial intelligence", "language model", "lm",
    "inline chat", "chat", "agent", "mcp", "model context protocol",
    "extension host", "extension api", "notebook", "jupyter",
    "terminal", "debug", "intellisense", "completion",
    "semantic", "symbol", "refactor",
]

# 重要な変更を示すキーワード
IMPORTANT_KEYWORDS = {
    "security": ["security", "vulnerability", "CVE"],
    "breaking": ["breaking", "deprecated", "removed"],
    "copilot": ["copilot", "language model api", "chat api"],
}

# カテゴリ分類キーワード（パターン順に優先度チェック）
CATEGORY_KEYWORDS = {
    "security": ["security", "vulnerability", "CVE"],
    "breaking": ["breaking", "removed", "deprecated"],
    "fix": ["fix", "fixed", "resolve", "bug"],
    "feature": ["feat", "add", "new", "support", "introduce", "enable"],
    "improvement": ["improve", "better", "enhance", "optimize", "update"],
}


def fetch_releases(limit: int = 10) -> list:
    """GitHub から releases を取得"""
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    response = requests.get(RELEASES_URL, headers=headers, params={"per_page": limit})
    response.raise_for_status()
    return response.json()


def extract_highlights(body: str) -> list[str]:
    """リリースノートから AI 関連変更を抽出（AI_RELEVANT_KEYWORDS でフィルタ）"""
    if not body:
        return []

    highlights = []
    lines = body.split("\n")

    for line in lines:
        line = line.strip()
        # リスト項目を抽出
        if line.startswith(("- ", "* ", "• ")):
            text = line.lstrip("-*• ").strip()
            # 空でなく、マージコミットでない場合
            if text and not text.startswith("Merge"):
                # AI 関連キーワードでフィルタ
                text_lower = text.lower()
                if any(kw in text_lower for kw in AI_RELEVANT_KEYWORDS):
                    highlights.append(text)

    return highlights[:20]  # 最大20件（VS Code はリリースノートが大きいため多めに）


def categorize_highlight(text: str) -> str:
    """ハイライト行のカテゴリを判定"""
    text_lower = text.lower()

    # 優先度順にチェック（security, breaking が最優先）
    for category in ["security", "breaking", "fix", "feature", "improvement"]:
        keywords = CATEGORY_KEYWORDS.get(category, [])
        for keyword in keywords:
            if keyword in text_lower:
                return category

    # デフォルトは improvement
    return "improvement"


def categorize_highlights(highlights: list[str]) -> list[dict]:
    """ハイライト一覧をカテゴリ付きで返す"""
    return [
        {"text": h, "category": categorize_highlight(h)}
        for h in highlights
    ]


def detect_importance(highlights: list[str]) -> dict:
    """重要な変更を検出"""
    importance = {"level": "normal", "tags": []}

    text = " ".join(highlights).lower()

    for category, keywords in IMPORTANT_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                importance["tags"].append(category)
                if category in ["security", "breaking"]:
                    importance["level"] = "high"
                elif importance["level"] != "high":
                    importance["level"] = "medium"
                break

    importance["tags"] = list(set(importance["tags"]))
    return importance


def translate_highlights(highlights: list[str]) -> list[str]:
    """highlights を日本語に翻訳"""
    if not highlights:
        return []

    try:
        client = anthropic.Anthropic()
        text = "\n".join(f"- {h}" for h in highlights)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": f"""以下の VS Code リリースノートを日本語に翻訳してください。
技術的な正確さを保ちつつ、簡潔に翻訳してください。
各行は「- 」で始めてください。

{text}"""
            }]
        )

        translated = []
        for line in response.content[0].text.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                translated.append(line[2:])

        return translated if translated else highlights
    except Exception as e:
        print(f"翻訳エラー: {e}")
        return []


def format_release(release: dict, translate: bool = False) -> dict:
    """GitHub release をフォーマット"""
    highlights = extract_highlights(release.get("body", ""))
    importance = detect_importance(highlights)

    highlights_ja = []
    if translate and highlights:
        print(f"  翻訳中: {release['tag_name']}...")
        highlights_ja = translate_highlights(highlights)

    result = {
        "version": release["tag_name"],
        "date": release["published_at"][:10],
        "link": release["html_url"],
        "highlights_en": highlights,
        "highlights_ja": highlights_ja,
        "categorized_highlights": categorize_highlights(highlights),
        "prerelease": release.get("prerelease", False),
        "importance": importance,
    }
    # アクションアイテムを生成
    result["action_items"] = generate_action_items_for_release(result)
    return result


def load_existing_releases() -> dict:
    """既存の vscode releases を読み込み"""
    releases_file = OUTPUT_DIR / "vscode_releases.json"
    if releases_file.exists():
        with open(releases_file) as f:
            return json.load(f)
    return {"updated_at": None, "releases": []}


def merge_release(existing: dict, new: dict) -> dict:
    """既存リリースと新規データをマージ（重要フィールドを落とさない）"""
    out = dict(existing)
    out.update(new)

    # 落としたくないフィールドは「新が空なら既存を残す」
    for key in ("action_items", "highlights_ja"):
        new_val = new.get(key)
        existing_val = existing.get(key)
        # 新が空/None/空リスト/空dictなら既存を保持
        if not new_val and existing_val:
            out[key] = existing_val

    return out


def save_releases(data: dict):
    """releases を保存（原子的保存 + 1世代バックアップ）"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    releases_file = OUTPUT_DIR / "vscode_releases.json"
    backup_file = OUTPUT_DIR / "vscode_releases.json.bak"
    tmp_file = OUTPUT_DIR / "vscode_releases.json.tmp"

    # 簡易バリデーション
    if not isinstance(data.get("releases"), list):
        raise ValueError("releases must be a list")
    for r in data["releases"]:
        if not r.get("version"):
            raise ValueError(f"release missing version: {r}")

    # 既存データから翻訳を復元（翻訳消失防止）
    existing = load_existing_releases()
    existing_map = {r["version"]: r for r in existing.get("releases", [])}
    for r in data["releases"]:
        version = r["version"]
        if version in existing_map:
            existing_r = existing_map[version]
            # highlights_ja が空で、既存に翻訳があれば復元
            if not r.get("highlights_ja") and existing_r.get("highlights_ja"):
                r["highlights_ja"] = existing_r["highlights_ja"]
                print(f"  翻訳復元: {version}")

    # 1世代バックアップ
    if releases_file.exists():
        import shutil
        shutil.copy2(releases_file, backup_file)

    # tmp に書いてから原子的に置換
    with open(tmp_file, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, releases_file)
    print(f"保存: {releases_file}")


def check_for_updates(translate: bool = True) -> dict:
    """更新をチェックして結果を返す"""
    existing = load_existing_releases()
    existing_versions = {r["version"] for r in existing.get("releases", [])}

    print(f"GitHub から {GITHUB_REPO} のリリースを取得中...")
    raw_releases = fetch_releases(limit=10)

    new_releases = []
    all_releases = []

    for release in raw_releases:
        version = release["tag_name"]
        existing_release = next((r for r in existing.get("releases", []) if r["version"] == version), None)

        if existing_release:
            formatted = existing_release
            # categorized_highlights は常に再生成（ロジック改善時に反映）
            formatted["categorized_highlights"] = categorize_highlights(formatted.get("highlights_en", []))
            # action_items は常に再生成
            formatted["action_items"] = generate_action_items_for_release(formatted)
            # 翻訳がない場合は翻訳を追加
            if translate and not formatted.get("highlights_ja") and formatted.get("highlights_en"):
                print(f"  翻訳中: {version}...")
                formatted["highlights_ja"] = translate_highlights(formatted.get("highlights_en", []))
        else:
            formatted = format_release(release, translate=translate)

        all_releases.append(formatted)

        if version not in existing_versions:
            new_releases.append(formatted)
            print(f"  新規: {formatted['version']} ({formatted['importance']['level']})")

    # 重要な更新があるかチェック
    important_updates = [r for r in new_releases if r["importance"]["level"] in ["high", "medium"]]

    result = {
        "updated_at": datetime.now().isoformat(),
        "releases": all_releases,
    }

    save_releases(result)

    return {
        "new_count": len(new_releases),
        "important_count": len(important_updates),
        "new_releases": new_releases,
        "important_updates": important_updates,
    }


def generate_action_items_for_release(release: dict) -> list:
    """単一リリースからアクションアイテムを生成"""
    items = []
    tags = release.get("importance", {}).get("tags", [])
    version = release.get("version", "unknown")

    if "security" in tags:
        items.append({
            "task": f"VS Code {version} に更新（セキュリティ修正）",
            "source_feature": "セキュリティ修正",
            "category": "security",
        })
    if "breaking" in tags:
        items.append({
            "task": f"VS Code {version} の破壊的変更を確認",
            "source_feature": "破壊的変更",
            "category": "breaking",
        })
    if "copilot" in tags:
        items.append({
            "task": f"VS Code {version} の Copilot/LM API 変更を確認",
            "source_feature": "Copilot/Language Model API 変更",
            "category": "copilot",
        })

    return items


def generate_action_items(important_updates: list) -> list:
    """重要な更新からアクションアイテムを生成"""
    items = []
    priority = 1

    for release in important_updates:
        tags = release["importance"]["tags"]

        if "security" in tags:
            items.append({
                "task": f"VS Code {release['version']} に更新（セキュリティ修正）",
                "source_feature": "セキュリティ修正",
                "priority": priority,
                "project": "VS Code",
                "category": "tooling",
                "source": "vscode",
            })
            priority += 1
        if "breaking" in tags:
            items.append({
                "task": f"VS Code {release['version']} の破壊的変更を確認",
                "source_feature": "破壊的変更",
                "priority": priority,
                "project": "VS Code",
                "category": "tooling",
                "source": "vscode",
            })
            priority += 1
        if "copilot" in tags:
            items.append({
                "task": f"VS Code {release['version']} の Copilot/LM API 変更を確認",
                "source_feature": "Copilot/Language Model API 変更",
                "priority": priority,
                "project": "VS Code",
                "category": "tooling",
                "source": "vscode",
            })
            priority += 1

    return items


def save_analysis(releases: list):
    """分析結果を vscode_analysis.json 形式で保存"""
    if not releases:
        return

    latest = releases[0]
    important = [r for r in releases if r.get("importance", {}).get("level") in ["high", "medium"]]
    action_items = generate_action_items(important) if important else []

    # dev_improvements を highlights_ja から生成
    dev_improvements = []
    highlights_ja = latest.get("highlights_ja") or []
    for highlight in highlights_ja:
        dev_improvements.append({
            "project": "VS Code",
            "suggestion": highlight,
            "source_feature": latest.get("version", "unknown"),
        })

    analysis = {
        "version": latest["version"],
        "analyzed_at": datetime.now().isoformat(),
        "action_items": action_items,
        "dev_improvements": dev_improvements,
        "business_opportunities": [],
    }

    analysis_file = OUTPUT_DIR / "vscode_analysis.json"
    with open(analysis_file, "w") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    print(f"分析保存: {analysis_file}")


if __name__ == "__main__":
    result = check_for_updates()

    print(f"\n=== 結果 ===")
    print(f"新規リリース: {result['new_count']}件")
    print(f"重要な更新: {result['important_count']}件")

    existing = load_existing_releases()
    save_analysis(existing.get("releases", []))

    if result["important_updates"]:
        print("\n重要な更新:")
        for r in result["important_updates"]:
            print(f"  - {r['version']}: {', '.join(r['importance']['tags'])}")
