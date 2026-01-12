# Quickstart

AI Update Radar の基本的な使い方。

## 前提条件

- Python 3.11+
- 各AI APIのアクセス権

## 週次サイクル

```
月曜: collectors/ 実行
火〜木: evaluators/ で評価
金曜: experiments/ で実験
土日: 週次サマリ作成
月曜: exports/ に出力
```

## 最初のステップ

1. `sources/` で監視対象を確認
2. `python collectors/run.py` で収集
3. `evaluators/` の結果を確認
4. Layer 3 なら `experiments/` で実験

## 次のステップ

- [収集の実行方法](guides/collecting.md)
- [評価の実行方法](guides/evaluating.md)
- [実験の作成方法](guides/experimenting.md)
