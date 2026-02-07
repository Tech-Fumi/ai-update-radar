"""
Zenn 記事 AI 評価器（段階フィルター方式 ②）

send_consultation（MCP）経由で LLM に記事を評価させる。
小バッチ（5件）+ 失敗時リトライ + フォールバック。
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from collectors.models import CollectedEntry

logger = logging.getLogger(__name__)


@dataclass
class ArticleEvaluation:
    """記事評価結果"""

    url: str
    title: str
    relevance: int  # 1-5: AIOS/インフラ自動化への転用可能性
    actionability: int  # 1-5: すぐに使えるか
    summary_ja: str  # 1行要約
    recommended_action: str  # "adopt" / "watch" / "skip"
    prefilter_score: int = 0  # セッション1の soft filter スコア
    source_topic: str = ""  # 収集元トピック
    evaluation_source: str = "llm"  # "llm" or "fallback"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvaluationResult:
    """評価バッチの結果"""

    evaluated_at: str = ""
    total: int = 0
    llm_evaluated: int = 0
    fallback_used: int = 0
    evaluations: list[ArticleEvaluation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "evaluated_at": self.evaluated_at,
            "total": self.total,
            "llm_evaluated": self.llm_evaluated,
            "fallback_used": self.fallback_used,
            "evaluations": [e.to_dict() for e in self.evaluations],
        }


def _parse_prefilter(entry: CollectedEntry) -> dict:
    """raw_content から prefilter データを取得"""
    try:
        return json.loads(entry.raw_content) if entry.raw_content else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class ArticleEvaluator:
    """Zenn 記事の AI 評価器（send_consultation 経由）"""

    BATCH_SIZE = 5

    def __init__(self, send_fn=None):
        """
        Args:
            send_fn: send_consultation 相当の関数。
                     None の場合は MCP 経由で呼び出す想定（CLI から注入）。
        """
        self.send_fn = send_fn

    def evaluate_batch(
        self, entries: list[CollectedEntry]
    ) -> EvaluationResult:
        """小バッチ評価（BATCH_SIZE 件ずつ評価）"""
        result = EvaluationResult(
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            total=len(entries),
        )

        for i in range(0, len(entries), self.BATCH_SIZE):
            batch = entries[i : i + self.BATCH_SIZE]
            try:
                batch_results = self._evaluate_chunk(batch)
                result.evaluations.extend(batch_results)
                result.llm_evaluated += len(batch_results)
            except Exception as e:
                logger.warning(f"バッチ評価失敗（{len(batch)}件）: {e}")
                # 失敗時は記事単位でリトライ
                for entry in batch:
                    try:
                        single = self._evaluate_chunk([entry])
                        result.evaluations.extend(single)
                        result.llm_evaluated += 1
                    except Exception as e2:
                        logger.warning(f"単体評価失敗: {entry.title[:30]}: {e2}")
                        result.evaluations.append(self._fallback_evaluation(entry))
                        result.fallback_used += 1

        return result

    def _build_prompt(self, entries: list[CollectedEntry]) -> str:
        """評価プロンプトを構築"""
        articles = []
        for i, entry in enumerate(entries):
            prefilter = _parse_prefilter(entry)
            articles.append(
                f"[{i+1}] タイトル: {entry.title}\n"
                f"    URL: {entry.url}\n"
                f"    要約: {entry.summary[:200]}\n"
                f"    トピック: {prefilter.get('source_topic', '')}\n"
                f"    prefilterスコア: {prefilter.get('prefilter_score', 0)}"
            )

        articles_text = "\n\n".join(articles)

        return f"""以下の技術記事を評価してください。
各記事について、AI運用自動化（MCP、Claude Code、DevOps、CI/CD、インフラ自動化）の
観点から転用可能性を判定してください。

## 記事一覧

{articles_text}

## 評価基準

- relevance (1-5): AI運用自動化への転用可能性（5=直接使える、1=無関係）
- actionability (1-5): すぐに使えるか（5=即日導入可、1=参考程度）
- summary_ja: 1行要約（日本語、30文字以内）
- recommended_action: "adopt"（採用推奨）/ "watch"（注視）/ "skip"（スキップ）

## 出力形式（厳密に従うこと）

JSON配列で出力してください。他のテキストは不要です。

```json
[
  {{"index": 1, "relevance": 4, "actionability": 3, "summary_ja": "MCPサーバーの新しい実装パターン", "recommended_action": "watch"}},
  ...
]
```"""

    def _evaluate_chunk(
        self, entries: list[CollectedEntry]
    ) -> list[ArticleEvaluation]:
        """send_consultation で小バッチ評価"""
        if not self.send_fn:
            raise RuntimeError("send_fn が設定されていません")

        prompt = self._build_prompt(entries)

        # send_consultation 呼び出し
        response = self.send_fn(
            situation=f"Zenn 記事 {len(entries)} 件の AI 評価",
            options=["評価結果を JSON で返す"],
            question=prompt,
            consultation_type="tech",
        )

        # レスポンスから JSON を抽出
        evaluations = self._parse_response(response, entries)
        return evaluations

    def _parse_response(
        self, response: str, entries: list[CollectedEntry]
    ) -> list[ArticleEvaluation]:
        """LLM レスポンスから評価結果をパース"""
        # JSON 部分を抽出
        json_str = self._extract_json(response)
        if not json_str:
            raise ValueError("レスポンスから JSON を抽出できません")

        raw_list = json.loads(json_str)
        if not isinstance(raw_list, list):
            raise ValueError("レスポンスが JSON 配列ではありません")

        results = []
        for item in raw_list:
            idx = item.get("index", 0) - 1
            if 0 <= idx < len(entries):
                entry = entries[idx]
                prefilter = _parse_prefilter(entry)
                results.append(
                    ArticleEvaluation(
                        url=entry.url,
                        title=entry.title,
                        relevance=max(1, min(5, int(item.get("relevance", 1)))),
                        actionability=max(1, min(5, int(item.get("actionability", 1)))),
                        summary_ja=str(item.get("summary_ja", ""))[:50],
                        recommended_action=item.get("recommended_action", "skip")
                        if item.get("recommended_action") in ("adopt", "watch", "skip")
                        else "skip",
                        prefilter_score=prefilter.get("prefilter_score", 0),
                        source_topic=prefilter.get("source_topic", ""),
                        evaluation_source="llm",
                    )
                )

        return results

    def _extract_json(self, text: str) -> Optional[str]:
        """テキストから JSON 配列部分を抽出"""
        # ```json ... ``` ブロックを探す
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            return text[start:end].strip()

        # ``` ... ``` ブロックを探す
        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            candidate = text[start:end].strip()
            if candidate.startswith("["):
                return candidate

        # [ から始まる JSON を探す
        for i, c in enumerate(text):
            if c == "[":
                # 対応する ] を探す
                depth = 0
                for j in range(i, len(text)):
                    if text[j] == "[":
                        depth += 1
                    elif text[j] == "]":
                        depth -= 1
                        if depth == 0:
                            return text[i : j + 1]
                break

        return None

    def _fallback_evaluation(
        self, entry: CollectedEntry
    ) -> ArticleEvaluation:
        """LLM 失敗時のフォールバック（soft filter スコアのみで判定）"""
        prefilter = _parse_prefilter(entry)
        score = prefilter.get("prefilter_score", 0)

        # スコアから簡易判定
        if score >= 3:
            action = "watch"
            relevance = 3
        elif score >= 1:
            action = "watch"
            relevance = 2
        else:
            action = "skip"
            relevance = 1

        return ArticleEvaluation(
            url=entry.url,
            title=entry.title,
            relevance=relevance,
            actionability=1,  # フォールバックでは判定不能
            summary_ja=entry.title[:30],
            recommended_action=action,
            prefilter_score=score,
            source_topic=prefilter.get("source_topic", ""),
            evaluation_source="fallback",
        )
