# 週次自動実行セットアップ

## 概要

毎週月曜日に自動で AI 関連の更新を収集し、exports/ にエクスポートする。

## 方法1: cron

```bash
# crontab -e で以下を追加
# 毎週月曜日 AM 9:00 に実行
0 9 * * 1 /home/fumi/ai-update-radar/scripts/weekly_collect.sh
```

## 方法2: systemd timer（推奨）

### サービスファイル作成

```bash
# ~/.config/systemd/user/ai-radar-weekly.service
cat << 'EOF' > ~/.config/systemd/user/ai-radar-weekly.service
[Unit]
Description=AI Update Radar Weekly Collection
After=network-online.target

[Service]
Type=oneshot
ExecStart=/home/fumi/ai-update-radar/scripts/weekly_collect.sh
WorkingDirectory=/home/fumi/ai-update-radar
Environment="PATH=/home/fumi/.local/bin:/usr/bin:/bin"

[Install]
WantedBy=default.target
EOF
```

### タイマーファイル作成

```bash
# ~/.config/systemd/user/ai-radar-weekly.timer
cat << 'EOF' > ~/.config/systemd/user/ai-radar-weekly.timer
[Unit]
Description=AI Update Radar Weekly Timer

[Timer]
OnCalendar=Mon 09:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
```

### 有効化

```bash
systemctl --user daemon-reload
systemctl --user enable ai-radar-weekly.timer
systemctl --user start ai-radar-weekly.timer

# 状態確認
systemctl --user list-timers
```

## 環境変数

`.env` ファイルに以下を設定（オプション）:

```bash
# GitHub API トークン（レート制限緩和用）
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
```

## 手動実行

```bash
# 週次収集（7日分）
./scripts/weekly_collect.sh

# 日次収集（1日分）
python -m collectors.cli collect --days 1

# 特定のソースのみ
python -m collectors.cli collect --days 7 --no-github --no-pages
```

## ログ確認

```bash
# 最新のログ
cat .private/logs/weekly_*.log | tail -50

# systemd ログ
journalctl --user -u ai-radar-weekly.service
```

## 週次運用フロー

| 曜日 | 作業 |
|------|------|
| 月曜 | 自動収集（cron/systemd） |
| 火-木 | exports/ を確認、重要なものをピックアップ |
| 金曜 | 重要な更新を実験（30-90分） |
| 週末 | docs/weekly/ にサマリを記載 |
