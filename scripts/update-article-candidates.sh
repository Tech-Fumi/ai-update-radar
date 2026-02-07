#!/bin/bash
# 記事候補の自動更新スクリプト
#
# Zenn 記事を収集 → LLM 評価 → article_candidates.json に出力
# フロントエンドで人間がレビュー・承認するためのデータを生成
#
# 前提: .env に SEND_CONSULTATION_URL が設定済み
#
# 使用例:
#   ./scripts/update-article-candidates.sh           # デフォルト（7日分）
#   ./scripts/update-article-candidates.sh --days 14 # 14日分

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/.private/logs"
LOG_FILE="$LOG_DIR/article_update_$(date +%Y%m%d_%H%M%S).log"
OUTPUT_PATH="$PROJECT_DIR/frontend/public/data/article_candidates.json"

# 引数（デフォルト: 7日分）
DAYS="7"
if [[ "${1:-}" == "--days" ]] && [[ -n "${2:-}" ]]; then
    DAYS="$2"
elif [[ -n "${1:-}" ]] && [[ "${1:-}" != "--days" ]]; then
    DAYS="$1"
fi

# ログディレクトリ作成
mkdir -p "$LOG_DIR"

# 環境変数読み込み
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# SEND_CONSULTATION_URL チェック
if [[ -z "${SEND_CONSULTATION_URL:-}" ]]; then
    echo "❌ SEND_CONSULTATION_URL が設定されていません" | tee -a "$LOG_FILE"
    echo "   .env に以下を追加してください:" | tee -a "$LOG_FILE"
    echo "   SEND_CONSULTATION_URL=http://100.110.236.96:8000/call" | tee -a "$LOG_FILE"
    exit 1
fi

echo "=== 記事候補更新 ===" | tee -a "$LOG_FILE"
echo "開始: $(date)" | tee -a "$LOG_FILE"
echo "対象: 過去 ${DAYS} 日" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Python 環境をアクティベート
if [[ -d "$PROJECT_DIR/.venv" ]]; then
    source "$PROJECT_DIR/.venv/bin/activate"
fi

cd "$PROJECT_DIR"

# Zenn 収集 + LLM 評価 → article_candidates.json に直接出力
python -m collectors.cli evaluate-articles \
    --days "$DAYS" \
    --output "$OUTPUT_PATH" \
    2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"

# 結果確認
if [[ -f "$OUTPUT_PATH" ]]; then
    ARTICLE_COUNT=$(python3 -c "import json; d=json.load(open('$OUTPUT_PATH')); print(len(d.get('evaluations', [])))" 2>/dev/null || echo "?")
    echo "✅ 完了: $OUTPUT_PATH ($ARTICLE_COUNT 件)" | tee -a "$LOG_FILE"
else
    echo "❌ 出力ファイルが生成されませんでした" | tee -a "$LOG_FILE"
    exit 1
fi

echo "終了: $(date)" | tee -a "$LOG_FILE"
