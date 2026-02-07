#!/usr/bin/env python3
"""
環境情報収集モジュール
- MCP 設定を収集
- 使用中のツール・機能を特定
- システム情報（OS等）を収集
- リリース分析の関連性判定に使用
"""

import json
import os
import platform
from pathlib import Path
from typing import Optional


def get_system_info() -> dict:
    """システム情報を取得"""
    system = platform.system().lower()  # linux, darwin, windows
    return {
        "os": system,
        "os_name": platform.system(),  # Linux, Darwin, Windows
        "os_version": platform.version(),
        "architecture": platform.machine(),
        # 他の OS 固有のキーワード（フィルタ用）
        "other_os_keywords": _get_other_os_keywords(system),
    }


def _get_other_os_keywords(current_os: str) -> list[str]:
    """他の OS を示すキーワードを返す（自分の OS と違うものをフィルタ用）"""
    if current_os == "linux":
        return ["macos", "mac os", "darwin", "windows", "win32", "win64"]
    elif current_os == "darwin":
        return ["windows", "win32", "win64", "linux"]
    elif current_os == "windows":
        return ["macos", "mac os", "darwin", "linux"]
    return []


def find_mcp_configs(base_dir: Optional[Path] = None) -> list[dict]:
    """全プロジェクトの .mcp.json を収集"""
    if base_dir is None:
        base_dir = Path.home()

    configs = []
    for mcp_file in base_dir.glob("*/.mcp.json"):
        try:
            with open(mcp_file) as f:
                data = json.load(f)
                configs.append({
                    "project": mcp_file.parent.name,
                    "path": str(mcp_file),
                    "servers": list(data.get("mcpServers", {}).keys()),
                    "config": data.get("mcpServers", {}),
                })
        except Exception as e:
            print(f"Warning: {mcp_file} の読み込みに失敗: {e}")

    return configs


def get_mcp_usage() -> dict:
    """MCP サーバーの使用状況を集計"""
    configs = find_mcp_configs()

    usage = {}
    for config in configs:
        for server in config["servers"]:
            if server not in usage:
                usage[server] = {
                    "projects": [],
                    "type": None,
                    "config": None,
                }
            usage[server]["projects"].append(config["project"])

            # 設定詳細を保存（最初に見つかったもの）
            if usage[server]["config"] is None:
                server_config = config["config"].get(server, {})
                usage[server]["type"] = server_config.get("type", "command")
                usage[server]["config"] = server_config

    return usage


def check_tool_usage(tool_name: str) -> dict:
    """特定ツールの使用状況を確認"""
    usage = get_mcp_usage()

    if tool_name.lower() in [k.lower() for k in usage.keys()]:
        # 大文字小文字を無視してマッチ
        actual_key = next(k for k in usage.keys() if k.lower() == tool_name.lower())
        info = usage[actual_key]
        return {
            "in_use": True,
            "projects": info["projects"],
            "type": info["type"],
            "config": info["config"],
        }

    return {
        "in_use": False,
        "projects": [],
        "type": None,
        "config": None,
    }


def get_claude_code_features() -> dict:
    """Claude Code の使用機能を検出"""
    features = {
        "hooks": False,
        "skills": False,
        "subagents": False,
        "plan_mode": False,
        "mcp_servers": [],
    }

    home = Path.home()

    # Hooks
    hooks_dir = home / ".claude" / "hooks"
    if hooks_dir.exists():
        features["hooks"] = len(list(hooks_dir.glob("*.sh"))) > 0

    # Skills (global)
    skills_dir = home / ".claude" / "skills"
    if skills_dir.exists():
        features["skills"] = len(list(skills_dir.glob("*.md"))) > 0

    # Project-level skills
    for project_dir in home.glob("*/.claude/skills"):
        if list(project_dir.glob("*.md")):
            features["skills"] = True
            break

    # MCP servers
    usage = get_mcp_usage()
    features["mcp_servers"] = list(usage.keys())

    return features


def get_codex_usage() -> dict:
    """Codex の使用状況を詳細に確認"""
    base_info = check_tool_usage("codex")

    if not base_info["in_use"]:
        return base_info

    home = Path.home()

    # Codex 固有の機能検出
    features = {
        "mcp_mode": True,  # MCP として使用中（常に True）
        "headless": True,  # MCP経由なら常に headless
        # 以下は設定状況（enabled / disabled / not_configured）
        "sandbox": "not_configured",
        "custom_model": "not_configured",
        "config_toml": "not_configured",
    }

    # config.toml の確認
    config_toml_path = home / ".codex" / "config.toml"
    if config_toml_path.exists():
        features["config_toml"] = "enabled"
        try:
            with open(config_toml_path) as f:
                config_content = f.read().lower()
                if "sandbox" in config_content:
                    features["sandbox"] = "enabled"
                if "model" in config_content:
                    features["custom_model"] = "enabled"
        except Exception:
            pass

    # wrapper スクリプトでの設定確認
    config = base_info.get("config", {})
    if config and "command" in config:
        wrapper_path = config["command"]
        if os.path.exists(wrapper_path):
            try:
                with open(wrapper_path) as f:
                    content = f.read().lower()
                    # --sandbox オプションがあれば有効
                    if "--sandbox" in content or "sandbox=true" in content:
                        features["sandbox"] = "enabled"
            except Exception:
                pass

    # 有効にすると使える機能のリスト
    features["available_features"] = []
    if features["sandbox"] == "not_configured":
        features["available_features"].append({
            "name": "sandbox",
            "description": "ファイルシステムの保護（読み取り専用マウント等）",
            "benefit": "コード生成時の意図しないファイル変更を防止",
        })
    if features["config_toml"] == "not_configured":
        features["available_features"].append({
            "name": "config.toml",
            "description": "Codex のカスタム設定ファイル",
            "benefit": "モデル指定、sandbox設定、ルール設定などをカスタマイズ",
        })
    if features["custom_model"] == "not_configured":
        features["available_features"].append({
            "name": "custom_model",
            "description": "使用するモデルの指定",
            "benefit": "タスクに応じて最適なモデルを選択可能",
        })

    base_info["features"] = features
    return base_info


def collect_environment() -> dict:
    """環境情報を一括収集"""
    return {
        "system": get_system_info(),
        "mcp_usage": get_mcp_usage(),
        "claude_code_features": get_claude_code_features(),
        "codex": get_codex_usage(),
        "tools_in_use": list(get_mcp_usage().keys()),
    }


if __name__ == "__main__":
    env = collect_environment()

    print("=== 環境情報 ===\n")

    print("【MCP サーバー】")
    for server, info in env["mcp_usage"].items():
        print(f"  {server}: {', '.join(info['projects'])}")

    print("\n【Claude Code 機能】")
    cc = env["claude_code_features"]
    print(f"  Hooks: {'✓' if cc['hooks'] else '✗'}")
    print(f"  Skills: {'✓' if cc['skills'] else '✗'}")
    print(f"  MCP servers: {len(cc['mcp_servers'])} 個")

    print("\n【Codex】")
    codex = env["codex"]
    print(f"  使用中: {'✓' if codex['in_use'] else '✗'}")
    if codex["in_use"]:
        print(f"  プロジェクト: {', '.join(codex['projects'])}")
        if codex.get("features"):
            print(f"  MCP モード: {'✓' if codex['features']['mcp_mode'] else '✗'}")
