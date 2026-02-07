#!/usr/bin/env python3
"""
Claude Code 更新分析エンジン

機能:
- プロジェクト設定の収集・分析
- リリースノートの AI 解析
- 開発視点での改善提案生成
- 経営視点での企画提案生成

使用例:
  python analyzer.py --release-notes "新機能: parallel tool calls"
  python analyzer.py --analyze-all
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# 外部ライブラリ
try:
    import requests
except ImportError:
    print("❌ requests が必要です: pip install requests")
    sys.exit(1)

# dotenv で環境変数を読み込み
try:
    from dotenv import load_dotenv

    # グローバルの .env を読み込む（ANTHROPIC_API_KEY がある）
    ENV_FILE = Path.home() / ".env"
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
except ImportError:
    pass  # dotenv がなければ環境変数から直接読む


# =============================================================================
# 設定
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
PROJECTS_CONFIG = SCRIPT_DIR / "config" / "projects.json"
ANALYSIS_OUTPUT_DIR = SCRIPT_DIR / "analysis"
RELEASES_JSON = SCRIPT_DIR.parent.parent / "frontend" / "public" / "data" / "releases.json"

# プロジェクトルート一覧（デフォルト）
DEFAULT_PROJECTS = [
    "/home/fumi/ScrimAutomationEngine",
    "/home/fumi/StreamFlowEngine",
    "/home/fumi/infra-automation",
    "/home/fumi/ai-company-os",
]

# Anthropic API（分析用）
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


# =============================================================================
# プロジェクト設定収集
# =============================================================================


def collect_project_info(project_root: str) -> dict:
    """プロジェクトの設定情報を収集"""
    project_path = Path(project_root)

    if not project_path.exists():
        return {"error": f"プロジェクトが見つかりません: {project_root}"}

    info = {
        "name": project_path.name,
        "path": str(project_path),
        "collected_at": datetime.now().isoformat(),
        "claude_md": None,
        "mcp_config": None,
        "package_json": None,
        "pyproject": None,
        "current_features": [],
        "pain_points": [],
        "business_context": None,
    }

    # CLAUDE.md を読み取り
    claude_md_path = project_path / "CLAUDE.md"
    if claude_md_path.exists():
        content = claude_md_path.read_text(encoding="utf-8")
        info["claude_md"] = {
            "exists": True,
            "size": len(content),
            "content_preview": content[:2000],
            "phases": extract_phases(content),
            "todos": extract_todos(content),
        }
        # ビジネスコンテキストを抽出
        info["business_context"] = extract_business_context(content)
        # 課題・Pain Points を抽出
        info["pain_points"] = extract_pain_points(content)

    # .mcp.json を読み取り
    mcp_config_path = project_path / ".mcp.json"
    if mcp_config_path.exists():
        try:
            mcp_data = json.loads(mcp_config_path.read_text())
            info["mcp_config"] = {
                "exists": True,
                "servers": list(mcp_data.get("mcpServers", {}).keys()),
            }
            info["current_features"].append("MCP サーバー連携")
        except json.JSONDecodeError:
            info["mcp_config"] = {"exists": True, "error": "パースエラー"}

    # package.json を読み取り（フロントエンド）
    package_json_path = project_path / "frontend" / "package.json"
    if not package_json_path.exists():
        package_json_path = project_path / "package.json"
    if package_json_path.exists():
        try:
            pkg_data = json.loads(package_json_path.read_text())
            info["package_json"] = {
                "exists": True,
                "name": pkg_data.get("name"),
                "dependencies": list(pkg_data.get("dependencies", {}).keys())[:20],
            }
        except json.JSONDecodeError:
            pass

    # pyproject.toml を読み取り
    pyproject_path = project_path / "pyproject.toml"
    if pyproject_path.exists():
        info["pyproject"] = {"exists": True}
        info["current_features"].append("Python バックエンド")

    # Claude Code 関連の使用状況を推測
    info["current_features"].extend(detect_claude_features(project_path))

    return info


def extract_phases(content: str) -> list:
    """CLAUDE.md からフェーズ情報を抽出"""
    phases = []
    phase_pattern = r"(?:Phase|フェーズ)\s*(\d+)[:\s]*(.+?)(?:\n|$)"
    for match in re.finditer(phase_pattern, content, re.IGNORECASE):
        phases.append(
            {
                "number": int(match.group(1)),
                "title": match.group(2).strip(),
            }
        )
    return phases


def extract_todos(content: str) -> dict:
    """CLAUDE.md から TODO 状況を抽出"""
    completed = len(re.findall(r"- \[x\]", content, re.IGNORECASE))
    pending = len(re.findall(r"- \[ \]", content))
    return {
        "completed": completed,
        "pending": pending,
        "total": completed + pending,
    }


def extract_business_context(content: str) -> Optional[dict]:
    """CLAUDE.md からビジネスコンテキストを抽出"""
    context = {}

    # プロジェクト概要を探す
    overview_match = re.search(
        r"##?\s*(?:プロジェクト概要|概要|Overview)\s*\n([\s\S]*?)(?=\n##|\Z)", content
    )
    if overview_match:
        context["overview"] = overview_match.group(1).strip()[:500]

    # 目的・ゴールを探す
    goal_match = re.search(
        r"##?\s*(?:目的|ゴール|目標|Goal|Purpose)\s*\n([\s\S]*?)(?=\n##|\Z)", content
    )
    if goal_match:
        context["goal"] = goal_match.group(1).strip()[:500]

    # ターゲットユーザーを探す
    user_match = re.search(
        r"(?:ターゲット|ユーザー|対象|Target)\s*[:：]\s*(.+)", content
    )
    if user_match:
        context["target_user"] = user_match.group(1).strip()

    return context if context else None


def extract_pain_points(content: str) -> list:
    """CLAUDE.md から課題・Pain Points を抽出"""
    pain_points = []

    # 課題セクションを探す
    issue_match = re.search(
        r"##?\s*(?:課題|問題|Issues?|Problems?|Pain Points?)\s*\n([\s\S]*?)(?=\n##|\Z)",
        content,
    )
    if issue_match:
        issues_text = issue_match.group(1)
        # リスト項目を抽出
        for line in issues_text.split("\n"):
            if line.strip().startswith(("-", "*", "・")):
                pain_points.append(line.strip().lstrip("-*・ "))

    # TODO の未完了項目も課題として扱う
    for match in re.finditer(r"- \[ \]\s*(.+)", content):
        if len(pain_points) < 10:  # 最大10件
            pain_points.append(f"未完了: {match.group(1)}")

    return pain_points[:10]


def detect_claude_features(project_path: Path) -> list:
    """プロジェクトで使用中の Claude Code 機能を検出"""
    features = []

    # .claude ディレクトリの存在確認
    claude_dir = project_path / ".claude"
    if claude_dir.exists():
        features.append("Claude Code 設定")

        # hooks の存在確認
        hooks_dir = claude_dir / "hooks"
        if hooks_dir.exists() and list(hooks_dir.glob("*.sh")):
            features.append("Claude Code Hooks")

        # commands の存在確認
        commands_dir = claude_dir / "commands"
        if commands_dir.exists() and list(commands_dir.glob("*.md")):
            features.append("カスタムスラッシュコマンド")

    # session-manager の使用確認
    sessions_dir = project_path / ".claude" / "sessions"
    if sessions_dir.exists():
        features.append("セッション管理")

    return features


def collect_all_projects(project_roots: list = None) -> dict:
    """全プロジェクトの情報を収集"""
    if project_roots is None:
        # projects.json があれば読み込み
        if PROJECTS_CONFIG.exists():
            config = json.loads(PROJECTS_CONFIG.read_text())
            project_roots = config.get("projects", DEFAULT_PROJECTS)
        else:
            project_roots = DEFAULT_PROJECTS

    results = {
        "collected_at": datetime.now().isoformat(),
        "projects": {},
    }

    for root in project_roots:
        print(f"📂 {Path(root).name} を収集中...")
        info = collect_project_info(root)
        results["projects"][info.get("name", root)] = info

    return results


# =============================================================================
# リリースノート分析
# =============================================================================


def get_release_details(version: str) -> Optional[dict]:
    """releases.json からバージョンの詳細情報を取得"""
    if not RELEASES_JSON.exists():
        return None

    try:
        data = json.loads(RELEASES_JSON.read_text())
        for release in data.get("releases", []):
            if release.get("version") == version:
                return release
    except Exception:
        pass
    return None


def enrich_release_notes(release_notes: str, version: str = None) -> str:
    """releases.json の詳細情報でリリースノートを補強"""
    if not version:
        # バージョン番号を抽出
        match = re.search(r'v?\d+\.\d+\.\d+', release_notes)
        if match:
            version = match.group()
            if not version.startswith('v'):
                version = 'v' + version

    if not version:
        return release_notes

    details = get_release_details(version)
    if not details:
        return release_notes

    # 詳細情報を追加
    enriched = [release_notes, "\n\n## 詳細解説（日本語）"]

    # highlights_ja を追加
    if details.get("highlights_ja"):
        enriched.append("\n### ハイライト")
        for h in details["highlights_ja"]:
            enriched.append(f"- {h}")

    # meanings を追加
    if details.get("meanings"):
        enriched.append("\n### 各機能の意味")
        for m in details["meanings"]:
            enriched.append(f"- **{m['title']}**: {m['meaning']}")

    return "\n".join(enriched)


def analyze_release_notes(release_notes: str, projects_info: dict, version: str = None) -> dict:
    """リリースノートを分析し、プロジェクトへの影響を評価"""

    # releases.json の詳細情報で補強
    enriched_notes = enrich_release_notes(release_notes, version)

    if not ANTHROPIC_API_KEY:
        return analyze_release_notes_simple(enriched_notes, projects_info)

    # AI による高度な分析
    return analyze_release_notes_ai(enriched_notes, projects_info)


def analyze_release_notes_simple(release_notes: str, projects_info: dict) -> dict:
    """シンプルなキーワードベースの分析"""
    analysis = {
        "analyzed_at": datetime.now().isoformat(),
        "method": "keyword_matching",
        "features_detected": [],
        "dev_improvements": [],
        "business_opportunities": [],
    }

    # キーワードマッチング
    keywords = {
        "performance": [
            "速度向上",
            "パフォーマンス改善",
            "高速化",
            "faster",
            "performance",
        ],
        "parallel": ["並列", "parallel", "concurrent", "同時実行"],
        "mcp": ["MCP", "Model Context Protocol", "サーバー"],
        "hooks": ["hooks", "フック", "トリガー"],
        "cost": ["コスト", "トークン", "効率", "cost", "token"],
        "api": ["API", "エンドポイント", "統合"],
        "automation": ["自動化", "automation", "auto"],
    }

    notes_lower = release_notes.lower()

    for category, words in keywords.items():
        for word in words:
            if word.lower() in notes_lower:
                analysis["features_detected"].append(
                    {
                        "category": category,
                        "keyword": word,
                    }
                )
                break

    # プロジェクトごとの提案生成
    detected_categories = [f["category"] for f in analysis["features_detected"]]

    for project_name, project_info in projects_info.get("projects", {}).items():
        if "error" in project_info:
            continue

        business_ctx = project_info.get("business_context", {})
        current_features = project_info.get("current_features", [])

        # 開発改善提案
        if "parallel" in detected_categories:
            if "MCP サーバー連携" in current_features:
                analysis["dev_improvements"].append(
                    {
                        "project": project_name,
                        "suggestion": "並列ツール呼び出しで MCP 処理を高速化",
                        "priority": "HIGH",
                        "estimated_impact": "処理時間 30-50% 削減見込み",
                    }
                )

        if "performance" in detected_categories:
            analysis["dev_improvements"].append(
                {
                    "project": project_name,
                    "suggestion": "パフォーマンス改善機能の適用検討",
                    "priority": "MEDIUM",
                    "estimated_impact": "応答速度改善",
                }
            )

        if "mcp" in detected_categories:
            if "MCP サーバー連携" in current_features:
                analysis["dev_improvements"].append(
                    {
                        "project": project_name,
                        "suggestion": "MCP キャッシュ機能の活用",
                        "priority": "MEDIUM",
                        "estimated_impact": "API 呼び出し削減",
                    }
                )

        # 経営視点の提案（より積極的に生成）
        if "automation" in detected_categories:
            business_ctx.get("overview", "") if business_ctx else ""
            analysis["business_opportunities"].append(
                {
                    "title": f"{project_name}: 自動化機能強化",
                    "description": "新しい自動化機能を活用してサービス価値を向上",
                    "affected_projects": [project_name],
                    "potential_value": "運用コスト削減・サービス差別化",
                    "action_required": "自動化可能な手動プロセスの洗い出し",
                }
            )

        if "parallel" in detected_categories:
            analysis["business_opportunities"].append(
                {
                    "title": f"{project_name}: 処理速度向上によるUX改善",
                    "description": "並列処理による高速化でユーザー体験を向上",
                    "affected_projects": [project_name],
                    "potential_value": "ユーザー満足度向上・離脱率低下",
                    "action_required": "並列化可能な処理の特定と実装",
                }
            )

        if "api" in detected_categories and business_ctx:
            analysis["business_opportunities"].append(
                {
                    "title": f"{project_name}: API 連携強化",
                    "description": "新しい API 機能で外部連携を拡大",
                    "affected_projects": [project_name],
                    "potential_value": "パートナーシップ機会・機能拡張",
                    "action_required": "連携可能な外部サービスの調査",
                }
            )

    # 重複排除
    seen_titles = set()
    unique_opportunities = []
    for opp in analysis["business_opportunities"]:
        title = opp.get("title", "")
        if title not in seen_titles:
            seen_titles.add(title)
            unique_opportunities.append(opp)
    analysis["business_opportunities"] = unique_opportunities

    return analysis


def analyze_release_notes_ai(release_notes: str, projects_info: dict) -> dict:
    """AI による高度な分析"""

    # プロジェクト情報をコンパクトに整形
    projects_summary = []
    for name, info in projects_info.get("projects", {}).items():
        if "error" in info:
            continue
        claude_md = info.get("claude_md") or {}
        projects_summary.append(
            {
                "name": name,
                "business_context": info.get("business_context"),
                "current_features": info.get("current_features", []),
                "pain_points": info.get("pain_points", [])[:5],
                "todos": claude_md.get("todos"),
            }
        )

    prompt = f"""あなたは "Release Notes Analyzer" です。
入力として与えられるリリースノート（変更点の文章）を読み、
ユーザーが取るべき対応を、誤解なく最小作業で提案してください。

# 最重要ルール（過剰解釈防止）
1) まず「帰属判定（誰/何の問題か）」を必ず行う。帰属判定なしにアクションを出してはいけない。
2) "Upstream（外部ツール/依存/OS/サービス側の修正）" と
   "Downstream（ユーザーの各プロジェクトにコード/設定変更が必要）" を必ず分類する。
3) Downstream だと確定できない限り、「全プロジェクトに適用」「全リポにPR」を提案してはいけない。
4) 不確実な場合は、"要確認" として質問ではなく「確認すべき観点」を列挙し、アクションは保留/最小にする。

# 用語
- Upstream: Claude Code本体 / CLIツール / OS / 依存ライブラリ / SaaS / ランタイム など "ユーザーのリポ外" の修正
- Downstream: ユーザーのリポジトリ内のコード/設定/運用手順変更が必要な修正

# 分類ルール（強制）
次の判定フローで分類せよ。

Step 1: リリースノートに "tool/product name" が含まれるか？
- 含まれる → Upstream の可能性が高い
- 含まれない → dependency か user's project の可能性

Step 2: "fixed security vulnerability" の対象はどこか？
- 権限判定/CLI挙動/実行基盤の修正 → Upstream
- ライブラリ脆弱性（CVE/パッケージ名） → Upstream(依存更新) だが適用は各リポ（=Mixedになりうる）
- ユーザーのコードの欠陥を示唆 → Downstream

Step 3: "全リポ適用" を許可する条件
- リリースノートが特定の依存（例: lodash, openssl 等）更新を要求し、複数リポがその依存を持つ可能性が高い
- または、共通テンプレ/共有モジュールをユーザーが運用している前提が明確
→ それ以外は全リポ適用禁止。対象リポの同定が必要。

# 入力

## リリースノート
{release_notes}

## ユーザーの既存プロジェクト情報
{json.dumps(projects_summary, ensure_ascii=False, indent=2)}

# 出力形式

以下の Markdown セクションを必ずこの順で出力し、最後に JSON を出力する。

## 0. Summary
- 1〜2行で要約（何が変わったか / 何をすべきか）

## 1. Attribution（帰属判定）
次の4項目を埋める（不明なら "Unknown"）
- Affected Component: {{例: Claude Code / OS / dependency:xx / user's project / CI runner}}
- Issue Type: {{security / bugfix / performance / behavior change / deprecation / new feature}}
- Patch Location: {{upgrade tool / upgrade dependency / change repo code / change config / change docs/runbook}}
- Classification: {{Upstream / Downstream / Mixed / Unknown}}

### Evidence
- リリースノートの該当文から、判断の根拠を短く箇条書き（引用は25語以内の抜粋にする）

## 2. Impact & Scope（影響と範囲）
- Scope Target: {{single machine / all dev machines / CI runners / specific repos / all repos}}
- Risk Level: {{Low/Med/High}}（理由も1行）
- Who is affected: {{例: Claude Code を実行する環境、特定のOS、特定の設定利用者}}

## 3. Required Actions（必須アクション）
ルール:
- Upstream の場合: "アップデート/ロールアウト/バージョン固定" が中心。リポへのPRは原則禁止。
- Downstream の場合: 対象リポと変更点を具体化。対象不明なら "要確認" とし、全リポ適用しない。

## 4. Optional Actions（任意/改善）
- "必須" ではない改善や監視（例: 監査ログ強化、検知追加）
- Downstream 断定がない場合は "要確認" を付ける

## 5. Anti-Patterns（やってはいけない誤解）
- 今回の内容で "誤ってやりがちな行動" を1〜3個
  例: 「全プロジェクトにパッチを当てる」など

## 6. Machine Output (JSON)

最後に、フロントエンド用の JSON を出力する。
**重要**: Upstream の修正（Classification == Upstream）の場合:
- action_items の project は "Claude Code" や "all dev environments" のようにツール/環境を指定
- 個別のユーザープロジェクト名を project に入れてはいけない
- category は "tooling" を使用

JSON形式:
{{
  "attribution": {{
    "affected_component": "...",
    "issue_type": "...",
    "patch_location": "...",
    "classification": "Upstream/Downstream/Mixed/Unknown",
    "scope_target": "...",
    "risk_level": "Low/Med/High"
  }},
  "dev_improvements": [
    {{
      "project": "プロジェクト名（Upstreamなら 'Claude Code' 等）",
      "suggestion": "具体的な改善提案",
      "source_feature": "この提案の元になったリリースノートの機能（日本語で簡潔に）",
      "what_it_is": "実際に何ができるようになったか。Before/Afterで説明（例: 以前は○○だった → 今は△△できる）。専門用語なしで具体的に",
      "merit": "これを使うと何が嬉しいか（具体的な場面で）",
      "demerit": "これを使うと何を失うか、または注意点",
      "target_area": "対象箇所",
      "expected_impact": "期待効果",
      "priority": "HIGH/MEDIUM/LOW",
      "effort": "導入工数の見積もり"
    }}
  ],
  "business_opportunities": [
    {{
      "title": "機会のタイトル",
      "source_feature": "この機会の元になったリリースノートの機能（日本語で簡潔に）",
      "what_it_is": "実際に何ができるようになったか。Before/Afterで説明（例: 以前は○○だった → 今は△△できる）。専門用語なしで具体的に",
      "merit": "これを活用すると何が嬉しいか（具体的な場面で）",
      "demerit": "リスクや注意点",
      "description": "詳細説明",
      "affected_projects": ["プロジェクト名"],
      "potential_value": "期待価値",
      "action_required": "必要なアクション"
    }}
  ],
  "action_items": [
    {{
      "task": "タスク内容（更新系なら対象バージョンを含める。例: 'Claude Code v2.1.7 に更新'）",
      "source_feature": "元になったリリースノートの機能（日本語で簡潔に）",
      "priority": 1,
      "project": "対象（Upstreamなら 'Claude Code' / 'all dev environments' 等）",
      "category": "dev/business/tooling"
    }}
  ],
  "anti_patterns": ["やってはいけない誤解1", "やってはいけない誤解2"]
}}
"""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        response.raise_for_status()

        result = response.json()
        content = result["content"][0]["text"]

        # JSON 部分を抽出
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            analysis = json.loads(json_match.group())
            analysis["analyzed_at"] = datetime.now().isoformat()
            analysis["method"] = "ai_analysis"
            return analysis

    except Exception as e:
        print(f"⚠️ AI 分析エラー: {e}")

    # フォールバック
    return analyze_release_notes_simple(release_notes, projects_info)


# =============================================================================
# 提案生成・出力
# =============================================================================


def generate_report(analysis: dict, projects_info: dict, version: str = None) -> str:
    """分析結果からレポートを生成"""

    report = []
    report.append("# Claude Code 更新影響分析レポート")
    report.append(f"\n生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"分析手法: {analysis.get('method', 'unknown')}")

    # 詳細ページへのリンク
    if version:
        report.append(f"\n📖 **詳細ページ**: http://localhost:3102/releases/{version}")

    # 開発視点
    report.append("\n## 🔧 開発視点での改善提案\n")

    dev_improvements = analysis.get("dev_improvements", [])
    if dev_improvements:
        for imp in dev_improvements:
            priority_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(
                imp.get("priority", "MEDIUM"), "⚪"
            )
            report.append(f"### {priority_emoji} {imp.get('project', 'Unknown')}")
            if imp.get("source_feature"):
                report.append(f"- **根拠**: `{imp['source_feature']}`")
            report.append(f"- **提案**: {imp.get('suggestion', '')}")
            if imp.get("target_area"):
                report.append(f"- **対象**: {imp['target_area']}")
            if imp.get("expected_impact"):
                report.append(f"- **期待効果**: {imp['expected_impact']}")
            if imp.get("effort"):
                report.append(f"- **工数**: {imp['effort']}")
            report.append("")
    else:
        report.append("_開発改善提案なし_\n")

    # 経営視点
    report.append("\n## 💼 経営視点での機会\n")

    opportunities = analysis.get("business_opportunities", [])
    if opportunities:
        for opp in opportunities:
            report.append(
                f"### 💡 {opp.get('title', opp.get('opportunity', 'Unknown'))}"
            )
            if opp.get("source_feature"):
                report.append(f"- **根拠**: `{opp['source_feature']}`")
            if opp.get("description"):
                report.append(f"{opp['description']}")
            if opp.get("affected_projects"):
                report.append(
                    f"- **関連プロジェクト**: {', '.join(opp['affected_projects'])}"
                )
            if opp.get("potential_value"):
                report.append(f"- **期待価値**: {opp['potential_value']}")
            if opp.get("action_required") or opp.get("action"):
                report.append(
                    f"- **アクション**: {opp.get('action_required') or opp.get('action')}"
                )
            report.append("")
    else:
        report.append("_ビジネス機会なし_\n")

    # アクションアイテム
    action_items = analysis.get("action_items", [])
    if action_items:
        report.append("\n## ✅ アクションアイテム（優先度順）\n")
        for i, item in enumerate(
            sorted(action_items, key=lambda x: x.get("priority", 99)), 1
        ):
            category_emoji = "🔧" if item.get("category") == "dev" else "💼"
            report.append(
                f"{i}. {category_emoji} [{item.get('project', 'General')}] {item.get('task', '')}"
            )
        report.append("")

    return "\n".join(report)


def save_analysis(analysis: dict, report: str, release_tag: str = None):
    """分析結果を保存"""
    ANALYSIS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag_suffix = f"_{release_tag}" if release_tag else ""

    # JSON 保存
    json_path = ANALYSIS_OUTPUT_DIR / f"analysis{tag_suffix}_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    # Markdown レポート保存
    md_path = ANALYSIS_OUTPUT_DIR / f"report{tag_suffix}_{timestamp}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)

    # releases.json に分析結果を統合
    if release_tag and RELEASES_JSON.exists():
        try:
            releases_data = json.loads(RELEASES_JSON.read_text())
            for release in releases_data.get("releases", []):
                if release.get("version") == release_tag:
                    # 分析結果を該当バージョンに追加
                    release["analysis"] = {
                        "dev_improvements": analysis.get("dev_improvements", []),
                        "business_opportunities": analysis.get("business_opportunities", []),
                        "action_items": analysis.get("action_items", []),
                        "analyzed_at": analysis.get("analyzed_at"),
                        "method": analysis.get("method"),
                    }
                    break
            # 更新を保存
            with open(RELEASES_JSON, "w", encoding="utf-8") as f:
                json.dump(releases_data, f, ensure_ascii=False, indent=2)
            print(f"📊 releases.json に分析結果を統合: {release_tag}")
        except Exception as e:
            print(f"⚠️ releases.json 更新エラー: {e}")

    print(f"📁 分析結果を保存: {json_path}")
    print(f"📄 レポートを保存: {md_path}")

    return json_path, md_path


# =============================================================================
# メイン処理
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Claude Code 更新分析エンジン")
    parser.add_argument(
        "--release-notes",
        "-r",
        help="分析するリリースノート（テキストまたはファイルパス）",
    )
    parser.add_argument(
        "--release-tag",
        "-t",
        help="リリースタグ（保存時のファイル名に使用）",
    )
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="プロジェクト情報の収集のみ（分析しない）",
    )
    parser.add_argument(
        "--analyze-all",
        action="store_true",
        help="最新のアーティファクトから自動分析",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="結果を JSON で出力",
    )

    args = parser.parse_args()

    print("🔬 Claude Code 更新分析エンジン")
    print("=" * 50)

    # プロジェクト情報収集
    print("\n📊 プロジェクト情報を収集中...")
    projects_info = collect_all_projects()

    if args.collect_only:
        if args.json:
            print(json.dumps(projects_info, ensure_ascii=False, indent=2))
        else:
            for name, info in projects_info["projects"].items():
                print(f"\n📂 {name}")
                print(f"   機能: {', '.join(info.get('current_features', []))}")
                if info.get("business_context"):
                    print(
                        f"   概要: {info['business_context'].get('overview', '')[:100]}..."
                    )
        return

    # リリースノート取得
    release_notes = None

    if args.release_notes:
        # パスっぽい文字列かつファイルが存在する場合のみ読み込み
        notes_path = Path(args.release_notes)
        if (
            len(args.release_notes) < 256
            and not args.release_notes.startswith("#")
            and notes_path.exists()
        ):
            release_notes = notes_path.read_text()
        else:
            release_notes = args.release_notes
    elif args.analyze_all:
        # 最新のアーティファクトを探す
        artifacts_dir = SCRIPT_DIR / "artifacts" / "claude_code"
        if artifacts_dir.exists():
            latest_dirs = sorted(artifacts_dir.iterdir(), reverse=True)
            if latest_dirs:
                for artifact_file in latest_dirs[0].glob("*.json"):
                    try:
                        data = json.loads(artifact_file.read_text())
                        if "change" in data and "details" in data["change"]:
                            details = data["change"]["details"]
                            if "body" in details:
                                release_notes = details["body"]
                                args.release_tag = details.get("tag", "unknown")
                                break
                    except:
                        pass

    if not release_notes:
        print("⚠️ リリースノートが指定されていません")
        print("使用例:")
        print('  python analyzer.py --release-notes "新機能: parallel tool calls"')
        print("  python analyzer.py --analyze-all")
        return

    print("\n📝 リリースノートを分析中...")
    print(f"   内容: {release_notes[:100]}...")
    if args.release_tag:
        print(f"   バージョン: {args.release_tag}")

    # 分析実行（releases.json の詳細情報も活用）
    analysis = analyze_release_notes(release_notes, projects_info, version=args.release_tag)

    # レポート生成
    report = generate_report(analysis, projects_info, version=args.release_tag)

    if args.json:
        print(json.dumps(analysis, ensure_ascii=False, indent=2))
    else:
        print("\n" + report)

    # 保存
    save_analysis(analysis, report, args.release_tag)

    print("\n" + "=" * 50)
    print("✅ 分析完了")


if __name__ == "__main__":
    main()
