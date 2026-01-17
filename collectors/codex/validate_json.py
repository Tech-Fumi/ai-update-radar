#!/usr/bin/env python3
"""
生成物JSON の整合性チェック

チェック項目:
1. JSON が parse できる
2. 期待キーが存在する
3. affected_indices が範囲外参照していない

実行方法:
    cd collectors/codex
    source ../claude_code/venv/bin/activate
    python validate_json.py
"""

import json
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "frontend" / "public" / "data"


def validate_releases_json():
    """codex_releases.json の整合性チェック"""
    errors = []
    releases_file = OUTPUT_DIR / "codex_releases.json"

    # 1. ファイル存在確認
    if not releases_file.exists():
        return [f"❌ ファイルが存在しません: {releases_file}"]

    # 2. JSON パース
    try:
        with open(releases_file) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"❌ JSON パースエラー: {e}"]

    # 3. 期待キーの確認（トップレベル）
    required_top_keys = ["updated_at", "releases"]
    for key in required_top_keys:
        if key not in data:
            errors.append(f"❌ 必須キーがありません: {key}")

    if "releases" not in data:
        return errors

    # 4. 各リリースの整合性チェック
    for i, release in enumerate(data["releases"]):
        version = release.get("version", f"release[{i}]")

        # 必須キー
        release_required_keys = ["version", "date", "link", "highlights_en", "importance"]
        for key in release_required_keys:
            if key not in release:
                errors.append(f"❌ {version}: 必須キー '{key}' がありません")

        # relevance の整合性
        relevance = release.get("relevance")
        if relevance:
            highlights_count = len(release.get("highlights_en", []))

            # affected_indices の範囲チェック
            for idx in relevance.get("affected_indices", []):
                if idx < 0 or idx >= highlights_count:
                    errors.append(
                        f"❌ {version}: affected_indices[{idx}] が範囲外 "
                        f"(highlights_en は {highlights_count} 件)"
                    )

            # opportunity_indices の範囲チェック
            for idx in relevance.get("opportunity_indices", []):
                if idx < 0 or idx >= highlights_count:
                    errors.append(
                        f"❌ {version}: opportunity_indices[{idx}] が範囲外 "
                        f"(highlights_en は {highlights_count} 件)"
                    )

            # other_indices の範囲チェック
            for idx in relevance.get("other_indices", []):
                if idx < 0 or idx >= highlights_count:
                    errors.append(
                        f"❌ {version}: other_indices[{idx}] が範囲外 "
                        f"(highlights_en は {highlights_count} 件)"
                    )

    return errors


def validate_analysis_json():
    """codex_analysis.json の整合性チェック"""
    errors = []
    analysis_file = OUTPUT_DIR / "codex_analysis.json"

    # 1. ファイル存在確認
    if not analysis_file.exists():
        return [f"❌ ファイルが存在しません: {analysis_file}"]

    # 2. JSON パース
    try:
        with open(analysis_file) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"❌ JSON パースエラー: {e}"]

    # 3. 期待キーの確認
    required_keys = ["version", "analyzed_at", "action_items", "dev_improvements"]
    for key in required_keys:
        if key not in data:
            errors.append(f"❌ 必須キーがありません: {key}")

    # 4. action_items の構造チェック
    for i, item in enumerate(data.get("action_items", [])):
        required_item_keys = ["task", "priority", "project"]
        for key in required_item_keys:
            if key not in item:
                errors.append(f"❌ action_items[{i}]: 必須キー '{key}' がありません")

    # 5. dev_improvements の構造チェック
    for i, item in enumerate(data.get("dev_improvements", [])):
        required_item_keys = ["project", "suggestion", "priority"]
        for key in required_item_keys:
            if key not in item:
                errors.append(f"❌ dev_improvements[{i}]: 必須キー '{key}' がありません")

    return errors


def validate_cross_reference():
    """releases と analysis の整合性チェック"""
    errors = []
    releases_file = OUTPUT_DIR / "codex_releases.json"
    analysis_file = OUTPUT_DIR / "codex_analysis.json"

    if not releases_file.exists() or not analysis_file.exists():
        return errors

    try:
        with open(releases_file) as f:
            releases_data = json.load(f)
        with open(analysis_file) as f:
            analysis_data = json.load(f)
    except json.JSONDecodeError:
        return errors

    # analysis.version が releases に存在するか
    analysis_version = analysis_data.get("version")
    release_versions = [r.get("version") for r in releases_data.get("releases", [])]

    if analysis_version and analysis_version not in release_versions:
        errors.append(
            f"❌ analysis.version '{analysis_version}' が releases に存在しません"
        )

    return errors


def main():
    print("=" * 60)
    print("生成物JSON 整合性チェック")
    print("=" * 60)

    all_errors = []

    # 1. codex_releases.json
    print("\n📁 codex_releases.json")
    errors = validate_releases_json()
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(f"  {e}")
    else:
        print("  ✅ OK")

    # 2. codex_analysis.json
    print("\n📁 codex_analysis.json")
    errors = validate_analysis_json()
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(f"  {e}")
    else:
        print("  ✅ OK")

    # 3. クロスリファレンス
    print("\n🔗 クロスリファレンス")
    errors = validate_cross_reference()
    if errors:
        all_errors.extend(errors)
        for e in errors:
            print(f"  {e}")
    else:
        print("  ✅ OK")

    # 結果サマリー
    print("\n" + "=" * 60)
    if all_errors:
        print(f"❌ {len(all_errors)} 件のエラーが見つかりました")
        sys.exit(1)
    else:
        print("✅ すべてのチェックに合格しました")
        sys.exit(0)


if __name__ == "__main__":
    main()
