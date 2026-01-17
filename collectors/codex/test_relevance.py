#!/usr/bin/env python3
"""
ゴールデンテスト: analyze_relevance の誤爆検知

実行方法:
    cd collectors/codex
    source ../claude_code/venv/bin/activate
    python test_relevance.py
"""

import sys
from monitor import analyze_relevance


def test_model_subclassification():
    """model カテゴリのサブ分類が正しく動作することを検証"""

    # 基本の env_info（MCP 使用中、custom_model 未設定）
    env_info = {
        "in_use": True,
        "projects": ["infra-automation"],
        "features": {
            "mcp_mode": True,
            "custom_model": False,  # 未設定
        },
        "system": {
            "os_name": "Linux",
            "other_os_keywords": ["windows", "macos", "darwin"],
        },
    }

    # ============================================
    # テストケース 1: App-server 系 → other (FYI)
    # ============================================
    highlights_appserver = [
        "App-server v2 now emits collaboration tool calls as item events in the turn stream, so clients can render agent coordination in real time. (#9213)",
    ]
    result = analyze_relevance(highlights_appserver, env_info)

    assert result["affected_indices"] == [], \
        f"App-server should be FYI, not affected. Got affected_indices={result['affected_indices']}"
    assert 0 in result["other_indices"], \
        f"App-server should be in other_indices. Got other_indices={result['other_indices']}"
    print("✅ Test 1 PASS: App-server → other (FYI)")

    # ============================================
    # テストケース 2: migration_markdown → other (model:metadata)
    # ============================================
    highlights_migration = [
        "`/models` metadata now includes upgrade migration_markdown so clients can display richer guidance when suggesting model upgrades. (#9219)",
    ]
    result = analyze_relevance(highlights_migration, env_info)

    assert result["affected_indices"] == [], \
        f"migration_markdown should be FYI. Got affected_indices={result['affected_indices']}"
    assert 0 in result["other_indices"], \
        f"migration_markdown should be in other_indices. Got other_indices={result['other_indices']}"
    print("✅ Test 2 PASS: migration_markdown → other (model:metadata)")

    # ============================================
    # テストケース 3: deprecation → affected (model:deprecation)
    # ============================================
    highlights_deprecation = [
        "The old model endpoint has been deprecated and will stop working in 30 days. (#9999)",
    ]
    result = analyze_relevance(highlights_deprecation, env_info)

    assert 0 in result["affected_indices"], \
        f"deprecation should be affected. Got affected_indices={result['affected_indices']}"
    assert result["other_indices"] == [], \
        f"deprecation should not be in other_indices. Got other_indices={result['other_indices']}"
    print("✅ Test 3 PASS: deprecation → affected (model:deprecation)")

    # ============================================
    # テストケース 4: breaking change → affected
    # ============================================
    highlights_breaking = [
        "Breaking: Default model changed from gpt-4 to gpt-5. Update your config if needed. (#9188)",
    ]
    result = analyze_relevance(highlights_breaking, env_info)

    assert 0 in result["affected_indices"], \
        f"breaking change should be affected. Got affected_indices={result['affected_indices']}"
    print("✅ Test 4 PASS: breaking change → affected")

    # ============================================
    # テストケース 5: model 一般（custom_model=False）→ other (model:neutral)
    # ============================================
    highlights_model_general = [
        "Added new model selection options for advanced users.",
    ]
    result = analyze_relevance(highlights_model_general, env_info)

    assert result["affected_indices"] == [], \
        f"model general (custom_model=False) should be FYI. Got affected_indices={result['affected_indices']}"
    assert 0 in result["other_indices"], \
        f"model general should be in other_indices. Got other_indices={result['other_indices']}"
    print("✅ Test 5 PASS: model general (custom_model=False) → other (model:neutral)")

    # ============================================
    # テストケース 6: model 一般（custom_model=True）→ affected (model:review)
    # ============================================
    env_info_custom = {**env_info, "features": {**env_info["features"], "custom_model": True}}
    result = analyze_relevance(highlights_model_general, env_info_custom)

    assert 0 in result["affected_indices"], \
        f"model general (custom_model=True) should be affected. Got affected_indices={result['affected_indices']}"
    print("✅ Test 6 PASS: model general (custom_model=True) → affected (model:review)")

    # ============================================
    # テストケース 7: MCP 関連 → affected
    # ============================================
    highlights_mcp = [
        "MCP CallToolResult now includes `threadId` in both `content` and `structuredContent`. (#9338)",
    ]
    result = analyze_relevance(highlights_mcp, env_info)

    assert 0 in result["affected_indices"], \
        f"MCP should be affected. Got affected_indices={result['affected_indices']}"
    print("✅ Test 7 PASS: MCP → affected")

    # ============================================
    # テストケース 8: 複合ケース（App-server + MCP 混在）
    # ============================================
    highlights_mixed = [
        "App-server v2 now emits collaboration tool calls as item events.",  # → other
        "MCP interface docs updated to reflect structured output schema.",   # → affected (mcp)
        "`/models` metadata now includes upgrade migration_markdown.",        # → other (model:metadata)
    ]
    result = analyze_relevance(highlights_mixed, env_info)

    assert result["affected_indices"] == [1], \
        f"Only MCP line should be affected. Got affected_indices={result['affected_indices']}"
    assert 0 in result["other_indices"] and 2 in result["other_indices"], \
        f"App-server and migration should be in other. Got other_indices={result['other_indices']}"
    print("✅ Test 8 PASS: 複合ケース（App-server + MCP 混在）")

    print("\n" + "=" * 50)
    print("全テスト PASS ✅")
    print("=" * 50)


if __name__ == "__main__":
    try:
        test_model_subclassification()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ テスト失敗: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        sys.exit(1)
