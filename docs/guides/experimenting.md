# 実験の作成方法

Layer 3 の変化に対して実験を行う手順。

## ルール

- **時間上限**: 30〜90分
- **隔離環境**: experiments/ 内のみ
- **記録必須**: README.md で結果を記録

## 手順

1. `experiments/` に新しいフォルダを作成
2. テンプレートをコピー

```bash
cp -r experiments/_template experiments/YYYY-MM-DD-experiment-name
```

3. 実験を実行
4. README.md に結果を記録

## 成果物の出力

採用決定した場合:

1. `exports/` に成果物を出力
2. 関連リポジトリに通知
