# Claude Code リリース監視

GitHub Releases の Atom フィードを監視し、新しいリリースがあれば Discord に通知する。

## セットアップ

```bash
cd /home/fumi/infra-automation/scripts/claude-code-monitor
pip install -r requirements.txt
```

## 環境変数

```bash
export CLAUDE_CODE_DISCORD_WEBHOOK="https://discord.com/api/webhooks/xxx/yyy"
```

## 手動実行

```bash
python monitor.py
```

## cron 設定（2時間ごと）

```bash
crontab -e
# 以下を追加
0 */2 * * * cd /home/fumi/infra-automation/scripts/claude-code-monitor && /usr/bin/python3 monitor.py >> /tmp/claude-code-monitor.log 2>&1
```

## 状態ファイル

`.last_release_state.json` に最後に確認したリリース ID が保存される。
このファイルを削除すると、次回実行時に最新リリースが通知される。
