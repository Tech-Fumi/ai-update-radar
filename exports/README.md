# Exports - 他リポジトリへの成果物

このリポジトリの成果を他のプロジェクトに渡すための出力先。

## 出力形式

### 1. 週次ダイジェスト

```json
{
  "week": "2025-W51",
  "highlights": [
    {
      "title": "...",
      "category": "capability",
      "impact": "high",
      "action": "experiment",
      "details_url": "..."
    }
  ],
  "experiments_completed": [...],
  "adopted": [...]
}
```

### 2. 採用決定リスト

他リポジトリで実装すべき変更：

```yaml
adopted:
  - id: "2025-12-21-xxx"
    target_repo: "infra-automation"
    action: "MCP サーバーに統合"
    priority: high
```

### 3. 技術アラート

即座に対応が必要な変更：

```yaml
alerts:
  - type: "breaking_change"
    source: "openai-api"
    message: "..."
    deadline: "2025-01-01"
```

## 連携先

| リポジトリ | 連携方法 |
|-----------|---------|
| infra-automation | exports/ を参照 |
| ScrimAutomationEngine | exports/ を参照 |
| StreamFlowEngine | exports/ を参照 |

## 自動化（将来）

- [ ] 週次で exports/ を自動生成
- [ ] 連携先に通知を送信
- [ ] decision-ledger に記録
