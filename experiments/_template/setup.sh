#!/bin/bash
# 新しい実験ディレクトリを作成するスクリプト
#
# 使い方:
#   ./experiments/_template/setup.sh "実験名"
#
# 例:
#   ./experiments/_template/setup.sh "claude-mcp-vision"

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <experiment-name>"
    echo "Example: $0 claude-mcp-vision"
    exit 1
fi

EXPERIMENT_NAME="$1"
DATE=$(date +%Y-%m-%d)
DIR_NAME="${DATE}-${EXPERIMENT_NAME}"
EXPERIMENT_DIR="experiments/${DIR_NAME}"

# ディレクトリ作成
if [ -d "$EXPERIMENT_DIR" ]; then
    echo "Error: Directory already exists: $EXPERIMENT_DIR"
    exit 1
fi

echo "Creating experiment: $DIR_NAME"

mkdir -p "$EXPERIMENT_DIR/src"
mkdir -p "$EXPERIMENT_DIR/data"
mkdir -p "$EXPERIMENT_DIR/results"

# テンプレートをコピー
cp experiments/_template/README.md "$EXPERIMENT_DIR/README.md"

# 日付と名前を置換
sed -i "s/YYYY-MM-DD/${DATE}/g" "$EXPERIMENT_DIR/README.md"
sed -i "s/{実験名}/${EXPERIMENT_NAME}/g" "$EXPERIMENT_DIR/README.md"

# .gitkeep を追加（空ディレクトリ保持用）
touch "$EXPERIMENT_DIR/src/.gitkeep"

echo ""
echo "Created: $EXPERIMENT_DIR"
echo ""
echo "Next steps:"
echo "  1. cd $EXPERIMENT_DIR"
echo "  2. Edit README.md with experiment details"
echo "  3. Start your 30-90 min experiment!"
echo ""
echo "Remember: If it takes longer than 90 min, stop and record why."
