from __future__ import annotations

from statistics import fmean
from typing import Any

from psychology.evaluation.runner import EvalRuntimeRow


def _word_overlap(a: str, b: str) -> float:
    a_set = {tok for tok in a.lower().split() if tok}
    b_set = {tok for tok in b.lower().split() if tok}
    if not a_set:
        return 0.0
    return len(a_set.intersection(b_set)) / len(a_set)


def run_ragas_eval(rows: list[EvalRuntimeRow]) -> dict[str, Any]:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
    except Exception:
        fallback_cases = []
        for row in rows:
            context_joined = " ".join(row.contexts)
            fallback_cases.append(
                {
                    "sample_id": row.sample_id,
                    "context_precision": _word_overlap(row.answer, context_joined),
                    "context_recall": _word_overlap(row.expected_answer, context_joined),
                    "faithfulness": _word_overlap(row.answer, context_joined),
                    "answer_relevancy": _word_overlap(row.answer, row.question),
                }
            )
        return {
            "engine": "fallback",
            "cases": fallback_cases,
            "aggregate": {
                "context_precision": fmean([c["context_precision"] for c in fallback_cases]) if fallback_cases else 0.0,
                "context_recall": fmean([c["context_recall"] for c in fallback_cases]) if fallback_cases else 0.0,
                "faithfulness": fmean([c["faithfulness"] for c in fallback_cases]) if fallback_cases else 0.0,
                "answer_relevancy": fmean([c["answer_relevancy"] for c in fallback_cases]) if fallback_cases else 0.0,
            },
        }

    payload = {
        "question": [row.question for row in rows],
        "answer": [row.answer for row in rows],
        "contexts": [row.contexts for row in rows],
        "ground_truth": [row.expected_answer for row in rows],
    }
    dataset = Dataset.from_dict(payload)
    ragas_result = evaluate(dataset=dataset, metrics=[context_precision, context_recall, faithfulness, answer_relevancy])
    table = ragas_result.to_pandas().to_dict(orient="records")
    cases = []
    for idx, row in enumerate(rows):
        item = table[idx] if idx < len(table) else {}
        cases.append(
            {
                "sample_id": row.sample_id,
                "context_precision": float(item.get("context_precision", 0.0) or 0.0),
                "context_recall": float(item.get("context_recall", 0.0) or 0.0),
                "faithfulness": float(item.get("faithfulness", 0.0) or 0.0),
                "answer_relevancy": float(item.get("answer_relevancy", 0.0) or 0.0),
            }
        )

    return {
        "engine": "ragas",
        "cases": cases,
        "aggregate": {
            "context_precision": fmean([c["context_precision"] for c in cases]) if cases else 0.0,
            "context_recall": fmean([c["context_recall"] for c in cases]) if cases else 0.0,
            "faithfulness": fmean([c["faithfulness"] for c in cases]) if cases else 0.0,
            "answer_relevancy": fmean([c["answer_relevancy"] for c in cases]) if cases else 0.0,
        },
    }

