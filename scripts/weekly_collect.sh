#!/bin/bash
# 週次収集スクリプト
# 毎週月曜日に実行することを想定

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
EXPORTS_DIR="$PROJECT_DIR/exports"
LOG_FILE="$PROJECT_DIR/.private/logs/weekly_$(date +%Y%m%d).log"

# ログディレクトリ作成
mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$EXPORTS_DIR"

# 環境変数読み込み（存在する場合）
if [[ -f "$PROJECT_DIR/.env" ]]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
fi

echo "=== AI Update Radar 週次収集 ===" | tee -a "$LOG_FILE"
echo "開始: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Python 環境をアクティベート（存在する場合）
if [[ -d "$PROJECT_DIR/.venv" ]]; then
    source "$PROJECT_DIR/.venv/bin/activate"
fi

# 収集実行（汎用コレクター: RSS + GitHub + PageDiff）
cd "$PROJECT_DIR"
python -m collectors.cli collect --days 7 --export 2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"

# VS Code リリース監視
echo "--- VS Code リリース収集 ---" | tee -a "$LOG_FILE"
python -m collectors.vscode.monitor 2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "完了: $(date)" | tee -a "$LOG_FILE"

# 成功時のサマリ
LATEST_EXPORT=$(ls -t "$EXPORTS_DIR"/collection_*.json 2>/dev/null | head -1)
if [[ -n "$LATEST_EXPORT" ]]; then
    ENTRY_COUNT=$(jq '.results | map(.entries | length) | add // 0' "$LATEST_EXPORT")
    echo "エクスポート: $LATEST_EXPORT ($ENTRY_COUNT 件)" | tee -a "$LOG_FILE"
fi
