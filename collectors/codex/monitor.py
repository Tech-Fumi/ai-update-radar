#!/usr/bin/env python3
"""
Codex (OpenAI) 軽量監視
- GitHub releases を取得
- 重要な変更（破壊的変更、セキュリティ）を検出
- releases.json に統合
"""

import json
import os
import re
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
import sys

# 親ディレクトリを追加して env_collector をインポート
sys.path.insert(0, str(Path(__file__).parent.parent))
from env_collector import get_codex_usage, get_system_info

GITHUB_REPO = "openai/codex"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "data"

# 重要な変更を示すキーワード
IMPORTANT_KEYWORDS = {
    "security": ["security", "vulnerability", "CVE", "exploit", "patch"],
    "breaking": ["breaking", "deprecated", "removed", "migration required"],
    "model": ["model", "gpt-5", "gpt-4", "default model"],
}

# カテゴリ分類キーワード（パターン順に優先度チェック）
CATEGORY_KEYWORDS = {
    "security": ["security", "vulnerability", "CVE", "exploit", "patch security"],
    "breaking": ["breaking", "removed", "deprecated", "migration required"],
    "fix": ["fix:", "fix ", "fixed", "no longer hang", "no longer crash", "no longer fail",
            "workaround", "crash", "bug", "correctly", "avoid ", "resolve", "prevent "],
    "feature": ["feat:", "feature:", "add ", "adds ", "added", "support ", "supports ",
                "enable ", "enables ", "new ", "introduce", "now includes", "now surfaces",
                "can now", "gained"],
    "improvement": ["improve", "better", "enhance", "optimize", "update", "refactor",
                   "reduce", "increase", "now accurate", "now respects", "now round-trips"],
}


def fetch_releases(limit: int = 10) -> list:
    """GitHub から releases を取得"""
    headers = {"Accept": "application/vnd.github.v3+json"}
    response = requests.get(RELEASES_URL, headers=headers, params={"per_page": limit})
    response.raise_for_status()
    return response.json()


def extract_highlights(body: str) -> list[str]:
    """リリースノートから主要な変更点を抽出"""
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
                highlights.append(text)

    return highlights[:10]  # 最大10件


def categorize_highlight(text: str) -> str:
    """ハイライト行のカテゴリを判定"""
    text_lower = text.lower()

    # 特定パターンの早期判定
    # "no longer X" パターンは fix（以前は問題があった）
    if "no longer" in text_lower:
        return "fix"

    # "now X" パターンの分類
    if "now includes" in text_lower or "now surfaces" in text_lower:
        return "feature"

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
    """highlights を日本語に翻訳（重要なリリースのみ）"""
    if not highlights:
        return []

    try:
        client = anthropic.Anthropic()
        text = "\n".join(f"- {h}" for h in highlights)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""以下の Codex (OpenAI CLI) リリースノートを日本語に翻訳してください。
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


def explain_highlights(highlights_ja: list[str], indices: list[int], env_info: dict) -> dict[int, str]:
    """影響がある変更に分かりやすい説明を追加（Before/After形式）"""
    if not indices or not highlights_ja:
        return {}

    # 対象の行を抽出
    target_lines = []
    for i in indices:
        if i < len(highlights_ja):
            target_lines.append(f"{i}: {highlights_ja[i]}")

    if not target_lines:
        return {}

    # 環境情報を取得
    projects = env_info.get("projects", [])
    features = env_info.get("features", {})
    env_context = f"MCP経由でCodexを使用中（プロジェクト: {', '.join(projects)}）"

    try:
        client = anthropic.Anthropic()
        text = "\n".join(target_lines)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": f"""以下の Codex リリースノートの各行について、専門用語を使わずに「Before/After」形式で説明してください。

ユーザー環境: {env_context}

各行の形式: "インデックス: 内容"

出力形式（各行ごとに）:
インデックス: 以前は〇〇だった → 今は△△できる

ルール:
- 専門用語（headless, sandbox, device-code等）は避けて、具体的に何ができるか説明
- 1行30文字以内で簡潔に
- ユーザーの環境に関連づけて説明

{text}"""
            }]
        )

        # パース（より柔軟に）
        raw_text = response.content[0].text
        explanations = {}

        for line in raw_text.split("\n"):
            line = line.strip()
            if not line or "→" not in line:
                continue

            # 様々な形式に対応: "0: ...", "- 0: ...", "・0: ..."
            cleaned = line.lstrip("-・• ")

            # インデックス抽出（数字で始まる部分を探す）
            match = re.match(r'^(\d+)[:：.]?\s*(.+)', cleaned)
            if match:
                try:
                    idx = int(match.group(1))
                    explanation = match.group(2).strip()
                    explanations[idx] = explanation
                except (ValueError, IndexError):
                    continue

        return explanations
    except Exception as e:
        print(f"説明生成エラー: {e}")
        return {}


def analyze_relevance(highlights: list[str], env_info: dict) -> dict:
    """環境に対する関連性を分析（3カテゴリに分類）"""
    relevance = {
        "applies_to_you": False,
        "reasons": [],
        "affected_indices": [],      # 有効な機能に影響（今すぐ影響）
        "opportunity_indices": [],   # 有効にすると使える（提案）
        "other_indices": [],         # その他
        "opportunities": [],         # 提案の詳細
    }

    if not env_info.get("in_use"):
        relevance["reasons"].append("Codex を使用していません")
        return relevance

    features = env_info.get("features", {})

    # プロジェクト情報
    projects = env_info.get("projects", [])
    if projects:
        relevance["reasons"].append(f"プロジェクト: {', '.join(projects)}")

    if not features.get("mcp_mode"):
        return relevance

    relevance["reasons"].append("MCP 経由で Codex を使用中")

    # 有効な機能に関連するキーワード（今すぐ影響）
    # NOTE: "server" は削除。"app-server" などにもマッチして誤検出を起こす。
    # MCP 関連の変更は "mcp" キーワードで十分に検出可能。
    # API 開発者向けの変更は capabilities.api_direct_usage で動的判定する（TODO）
    enabled_keywords = {
        "headless": ["headless", "sign-in", "login", "auth", "browser"],
        "mcp": ["mcp"],  # "server" は一般的すぎるため削除（"app-server" 等に誤マッチ）
        "api": ["api", "model", "default model", "gpt-"],
    }

    # 無効だが有効にすると使えるキーワード
    feature_keywords = {
        "sandbox": {
            "keywords": ["sandbox", "read-only", "protect", "mount"],
            "benefit": "ファイルシステムの保護が強化されます",
        },
        "config_toml": {
            "keywords": ["config.toml", "config file", "configuration", "setting"],
            "benefit": "Codex の動作をカスタマイズできます",
        },
        "custom_model": {
            "keywords": ["model", "gpt-"],
            "benefit": "タスクに応じて最適なモデルを選択できます",
        },
    }

    # OS 情報を取得（env_collector で一元管理）
    system_info = env_info.get("system", {})
    other_os_keywords = system_info.get("other_os_keywords", [])

    # 各行を分類
    for i, line in enumerate(highlights):
        line_lower = line.lower()
        categorized = False

        # 0. 他の OS 固有の話なら「その他」
        if any(os_kw in line_lower for os_kw in other_os_keywords):
            relevance["other_indices"].append(i)
            continue

        # 1. 有効な機能に関連？
        for feature, keywords in enabled_keywords.items():
            if any(kw in line_lower for kw in keywords):
                relevance["affected_indices"].append(i)
                categorized = True
                break

        if categorized:
            continue

        # 2. 有効にすると使える機能に関連？
        # ただしドキュメント系（docs, schema, publish）は除外
        doc_keywords = ["docs/", "schema", "publish", "document", "generate"]
        is_doc_update = any(dk in line_lower for dk in doc_keywords)

        for feature_name, info in feature_keywords.items():
            feature_status = features.get(feature_name, "not_configured")
            if feature_status == "not_configured":
                if any(kw in line_lower for kw in info["keywords"]) and not is_doc_update:
                    relevance["opportunity_indices"].append(i)
                    # 提案を追加（重複排除）
                    if not any(o["feature"] == feature_name for o in relevance["opportunities"]):
                        relevance["opportunities"].append({
                            "feature": feature_name,
                            "benefit": info["benefit"],
                            "projects": projects,
                        })
                    categorized = True
                    break

        if categorized:
            continue

        # 3. その他
        relevance["other_indices"].append(i)

    # 影響または提案があれば applies_to_you = True
    if relevance["affected_indices"] or relevance["opportunity_indices"]:
        relevance["applies_to_you"] = True

    return relevance


def format_release(release: dict, translate: bool = False, env_info: dict = None) -> dict:
    """GitHub release をフォーマット"""
    highlights = extract_highlights(release.get("body", ""))
    importance = detect_importance(highlights)

    highlights_ja = []
    if translate and highlights:
        print(f"  翻訳中: {release['tag_name']}...")
        highlights_ja = translate_highlights(highlights)

    # 環境関連性分析
    relevance = None
    explanations = {}
    if env_info and importance["level"] != "normal":
        relevance = analyze_relevance(highlights, env_info)

        # 影響がある変更 + 有効にすると使える変更に説明を追加
        if relevance and highlights_ja:
            indices_to_explain = (relevance.get("affected_indices", []) +
                                  relevance.get("opportunity_indices", []))
            if indices_to_explain:
                print(f"  説明生成中: {release['tag_name']}...")
                explanations = explain_highlights(
                    highlights_ja,
                    indices_to_explain,
                    env_info
                )

    result = {
        "version": release["tag_name"],
        "date": release["published_at"][:10],
        "link": release["html_url"],
        "highlights_en": highlights,
        "highlights_ja": highlights_ja,
        "categorized_highlights": categorize_highlights(highlights),  # カテゴリ付き
        "explanations": explanations,  # インデックス -> 説明 のマップ
        "prerelease": release.get("prerelease", False),
        "importance": importance,
        "relevance": relevance,
    }
    # アクションアイテムを生成
    result["action_items"] = generate_action_items_for_release(result)
    return result


def load_existing_releases() -> dict:
    """既存の codex releases を読み込み"""
    releases_file = OUTPUT_DIR / "codex_releases.json"
    if releases_file.exists():
        with open(releases_file) as f:
            return json.load(f)
    return {"updated_at": None, "releases": []}


def merge_release(existing: dict, new: dict) -> dict:
    """既存リリースと新規データをマージ（重要フィールドを落とさない）"""
    out = dict(existing)
    out.update(new)

    # 落としたくないフィールドは「新が空なら既存を残す」
    for key in ("action_items", "relevance", "explanations"):
        new_val = new.get(key)
        existing_val = existing.get(key)
        # 新が空/None/空リスト/空dictなら既存を保持
        if not new_val and existing_val:
            out[key] = existing_val

    return out


def save_releases(data: dict):
    """releases を保存（原子的保存 + 1世代バックアップ）"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    releases_file = OUTPUT_DIR / "codex_releases.json"
    backup_file = OUTPUT_DIR / "codex_releases.json.bak"
    tmp_file = OUTPUT_DIR / "codex_releases.json.tmp"

    # 簡易バリデーション
    if not isinstance(data.get("releases"), list):
        raise ValueError("releases must be a list")
    for r in data["releases"]:
        if not r.get("version"):
            raise ValueError(f"release missing version: {r}")

    # 1世代バックアップ
    if releases_file.exists():
        import shutil
        shutil.copy2(releases_file, backup_file)

    # tmp に書いてから原子的に置換
    with open(tmp_file, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    import os
    os.replace(tmp_file, releases_file)
    print(f"保存: {releases_file}")


def check_for_updates(translate: bool = True) -> dict:
    """更新をチェックして結果を返す"""
    existing = load_existing_releases()
    existing_versions = {r["version"] for r in existing.get("releases", [])}

    # 環境情報を取得
    print("環境情報を収集中...")
    env_info = get_codex_usage()
    env_info["system"] = get_system_info()  # システム情報を追加
    print(f"  OS: {env_info['system']['os_name']}")
    print(f"  Codex 使用中: {'✓' if env_info.get('in_use') else '✗'}")
    if env_info.get("projects"):
        print(f"  プロジェクト: {', '.join(env_info['projects'])}")

    print(f"\nGitHub から {GITHUB_REPO} のリリースを取得中...")
    raw_releases = fetch_releases(limit=10)

    new_releases = []
    all_releases = []

    for release in raw_releases:
        # 既存リリースは翻訳済みデータを再利用（ただし relevance は再計算）
        version = release["tag_name"]
        existing_release = next((r for r in existing.get("releases", []) if r["version"] == version), None)

        if existing_release:
            formatted = existing_release
            # categorized_highlights は常に再生成（ロジック改善時に反映）
            formatted["categorized_highlights"] = categorize_highlights(formatted.get("highlights_en", []))
            # action_items は常に再生成
            formatted["action_items"] = generate_action_items_for_release(formatted)
            # 翻訳がない場合は翻訳を追加（表示用）
            if translate and not formatted.get("highlights_ja") and formatted.get("highlights_en"):
                print(f"  翻訳中: {version}...")
                formatted["highlights_ja"] = translate_highlights(formatted.get("highlights_en", []))
            # relevance は条件付きで再計算
            # 1) importance が normal 以外 → 再計算
            # 2) relevance が空/無効 → 再計算
            rel = formatted.get("relevance")
            if formatted.get("importance", {}).get("level") != "normal":
                formatted["relevance"] = analyze_relevance(formatted.get("highlights_en", []), env_info)
            elif not rel or not isinstance(rel, dict):
                formatted["relevance"] = analyze_relevance(formatted.get("highlights_en", []), env_info)

            # explanations が不完全なら再生成（relevance が存在する場合）
            if formatted.get("relevance"):
                indices_to_explain = (formatted["relevance"].get("affected_indices", []) +
                                      formatted["relevance"].get("opportunity_indices", []))
                existing_explanations = formatted.get("explanations", {})
                missing = [i for i in indices_to_explain if str(i) not in existing_explanations]

                if missing:
                    print(f"  説明再生成中: {version}（{len(missing)}件不足）...")
                    new_explanations = explain_highlights(
                        formatted.get("highlights_ja", []),
                        indices_to_explain,
                        env_info
                    )
                    formatted["explanations"] = {**existing_explanations, **new_explanations}
        else:
            formatted = format_release(release, translate=translate, env_info=env_info)

        all_releases.append(formatted)

        if version not in existing_versions:
            new_releases.append(formatted)
            relevance = formatted.get("relevance")
            rel_mark = "🎯" if relevance and relevance.get("applies_to_you") else ""
            print(f"  新規: {formatted['version']} ({formatted['importance']['level']}) {rel_mark}")

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
    relevance = release.get("relevance") or {}
    version = release.get("version", "unknown")

    if "security" in tags:
        items.append({
            "task": f"Codex {version} に更新（セキュリティ修正）",
            "source_feature": "セキュリティ修正",
            "category": "security",
        })
    if "breaking" in tags:
        items.append({
            "task": f"Codex {version} の破壊的変更を確認",
            "source_feature": "破壊的変更",
            "category": "breaking",
        })
    if "model" in tags:
        items.append({
            "task": f"Codex {version} のモデル変更を確認",
            "source_feature": "デフォルトモデル変更",
            "category": "model",
        })

    # opportunities からもアクションアイテムを生成
    for opp in relevance.get("opportunities", []):
        items.append({
            "task": f"{opp['feature']} を有効化: {opp['benefit']}",
            "source_feature": f"機能提案: {opp['feature']}",
            "category": "opportunity",
        })

    # affected からアクションアイテムを生成
    for affected in relevance.get("affected", []):
        items.append({
            "task": f"{affected['feature']} の影響を確認",
            "source_feature": affected.get("reason", "環境に影響"),
            "category": "affected",
        })

    return items


def generate_action_items(important_updates: list) -> list:
    """重要な更新からアクションアイテムを生成（互換性維持）"""
    items = []
    priority = 1

    for release in important_updates:
        tags = release["importance"]["tags"]
        relevance = release.get("relevance") or {}

        if "security" in tags:
            items.append({
                "task": f"Codex {release['version']} に更新（セキュリティ修正）",
                "source_feature": "セキュリティ修正",
                "priority": priority,
                "project": "MCP Codex",
                "category": "tooling",
                "source": "codex",
            })
            priority += 1
        elif "breaking" in tags:
            items.append({
                "task": f"Codex {release['version']} の破壊的変更を確認",
                "source_feature": "破壊的変更",
                "priority": priority,
                "project": "MCP Codex",
                "category": "tooling",
                "source": "codex",
            })
            priority += 1
        elif "model" in tags:
            items.append({
                "task": f"Codex {release['version']} のモデル変更を確認",
                "source_feature": "デフォルトモデル変更",
                "priority": priority,
                "project": "MCP Codex",
                "category": "tooling",
                "source": "codex",
            })
            priority += 1

        # opportunities からもアクションアイテムを生成
        for opp in relevance.get("opportunities", []):
            items.append({
                "task": f"{opp['feature']} を有効化: {opp['benefit']}",
                "source_feature": f"機能提案: {opp['feature']}",
                "priority": priority,
                "project": ", ".join(opp.get("projects", ["MCP Codex"])),
                "category": "tooling",
                "source": "codex",
            })
            priority += 1

    return items


def save_analysis(releases: list):
    """分析結果を analysis.json 形式で保存"""
    # 重要なリリースを抽出
    important = [r for r in releases if r.get("importance", {}).get("level") in ["high", "medium"]]
    if not important:
        return

    latest = important[0]
    action_items = generate_action_items(important)

    # dev_improvements に詳細を追加
    dev_improvements = []
    relevance = latest.get("relevance") or {}
    explanations = latest.get("explanations") or {}
    highlights_ja = latest.get("highlights_ja") or []

    # affected_indices の詳細
    for idx in relevance.get("affected_indices", []):
        if idx < len(highlights_ja):
            dev_improvements.append({
                "project": "MCP Codex",
                "suggestion": highlights_ja[idx],
                "source_feature": f"影響あり (index {idx})",
                "what_it_is": explanations.get(str(idx), ""),
                "priority": "HIGH",
            })

    # opportunity_indices の詳細
    for idx in relevance.get("opportunity_indices", []):
        if idx < len(highlights_ja):
            dev_improvements.append({
                "project": "MCP Codex",
                "suggestion": highlights_ja[idx],
                "source_feature": f"機能提案 (index {idx})",
                "what_it_is": explanations.get(str(idx), ""),
                "priority": "MEDIUM",
            })

    analysis = {
        "version": latest["version"],
        "analyzed_at": datetime.now().isoformat(),
        "action_items": action_items,
        "dev_improvements": dev_improvements,
        "business_opportunities": [],
        "explanations": explanations,  # Before/After 説明
    }

    analysis_file = OUTPUT_DIR / "codex_analysis.json"
    with open(analysis_file, "w") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    print(f"分析保存: {analysis_file}")


if __name__ == "__main__":
    result = check_for_updates()

    print(f"\n=== 結果 ===")
    print(f"新規リリース: {result['new_count']}件")
    print(f"重要な更新: {result['important_count']}件")

    # 既存リリースからも分析を保存（重要なものがあれば）
    existing = load_existing_releases()
    save_analysis(existing.get("releases", []))

    if result["important_updates"]:
        print("\n重要な更新:")
        for r in result["important_updates"]:
            print(f"  - {r['version']}: {', '.join(r['importance']['tags'])}")

        action_items = generate_action_items(result["important_updates"])
        if action_items:
            print("\nアクションアイテム:")
            for item in action_items:
                print(f"  [{item['priority']}] {item['task']}")
