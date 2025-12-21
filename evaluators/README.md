# Evaluators - 影響判定ロジック

収集した情報を評価し、Layer 2/3 の判断を行う。

## 評価フロー

```
収集データ
    ↓
1. カテゴリ分類（能力/制限/価格）
    ↓
2. 関連性スコアリング
    ↓
3. Layer 判定（無視/検知のみ/深掘り）
    ↓
4. 判断ログ出力
```

## 評価基準

### 1. カテゴリ分類

| カテゴリ | キーワード例 |
|---------|-------------|
| capability | model, feature, agent, tool, vision, memory |
| constraint | limit, rate, context, token, region |
| pricing | price, cost, tier, plan, free, credit |
| other | UI, dashboard, documentation |

### 2. 関連性スコアリング

現在の運用に対する影響度を 0-10 で評価。

| スコア | 意味 |
|:------:|------|
| 9-10 | 即座に採用検討すべき |
| 7-8 | 深掘り対象 |
| 4-6 | 検知のみ、様子見 |
| 0-3 | 無視 |

#### スコアリング要素

- **直接適用可能性**: 今のシステムにそのまま入るか
- **コスト削減**: 時間 or 費用の削減が見込めるか
- **リスク**: 導入リスクは低いか
- **緊急性**: 競合優位性に影響するか

### 3. Layer 判定

| スコア | Layer | アクション |
|:------:|:-----:|-----------|
| 7+ | 3 | 実験 → experiments/ |
| 4-6 | 2 | 週次サマリに記載 |
| 0-3 | 1 | 記録のみ、無視 |

## 出力フォーマット

```yaml
entry:
  title: "..."
  source: "..."
  url: "..."

evaluation:
  category: capability
  relevance_score: 8
  layer: 3

  scoring_breakdown:
    applicability: 9   # 直接適用可能
    cost_reduction: 7  # コスト削減
    risk: 8           # 低リスク
    urgency: 8        # 競合優位性

  decision: experiment
  reason: |
    現在の MCP サーバー群に直接適用可能。
    Agent 間通信の効率化が見込める。

  next_action: "experiments/2025-12-21-agent-protocol/"
```

## 実装予定

- [ ] category_classifier.py
- [ ] relevance_scorer.py
- [ ] layer_decider.py
- [ ] evaluation_logger.py
