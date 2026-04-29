from __future__ import annotations

import math
from statistics import fmean
from typing import Any

from psychology.evaluation.llm_keys import groq_api_key, groq_eval_model_name
from psychology.evaluation.runner import EvalRuntimeRow


def _word_overlap(a: str, b: str) -> float:
    a_set = {tok for tok in a.lower().split() if tok}
    b_set = {tok for tok in b.lower().split() if tok}
    if not a_set:
        return 0.0
    return len(a_set.intersection(b_set)) / len(a_set)


def _safe_float(value: Any) -> float:
    try:
        out = float(value)
    except Exception:
        return 0.0
    if math.isnan(out) or math.isinf(out):
        return 0.0
    return out


def _lexical_fallback(rows: list[EvalRuntimeRow], reason: str) -> dict[str, Any]:
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
        "fallback_reason": reason,
        "cases": fallback_cases,
        "aggregate": {
            "context_precision": fmean([c["context_precision"] for c in fallback_cases]) if fallback_cases else 0.0,
            "context_recall": fmean([c["context_recall"] for c in fallback_cases]) if fallback_cases else 0.0,
            "faithfulness": fmean([c["faithfulness"] for c in fallback_cases]) if fallback_cases else 0.0,
            "answer_relevancy": fmean([c["answer_relevancy"] for c in fallback_cases]) if fallback_cases else 0.0,
        },
    }


def _cases_from_result(ragas_result: Any, rows: list[EvalRuntimeRow]) -> list[dict[str, Any]]:
    table = ragas_result.to_pandas().to_dict(orient="records")
    cases = []
    for idx, row in enumerate(rows):
        item = table[idx] if idx < len(table) else {}
        cases.append(
            {
                "sample_id": row.sample_id,
                "context_precision": _safe_float(item.get("context_precision", 0.0)),
                "context_recall": _safe_float(item.get("context_recall", 0.0)),
                "faithfulness": _safe_float(item.get("faithfulness", 0.0)),
                "answer_relevancy": _safe_float(item.get("answer_relevancy", 0.0)),
            }
        )
    return cases


def _success_payload(engine: str, ragas_result: Any, rows: list[EvalRuntimeRow]) -> dict[str, Any]:
    cases = _cases_from_result(ragas_result, rows)
    return {
        "engine": engine,
        "fallback_reason": None,
        "cases": cases,
        "aggregate": {
            "context_precision": fmean([c["context_precision"] for c in cases]) if cases else 0.0,
            "context_recall": fmean([c["context_recall"] for c in cases]) if cases else 0.0,
            "faithfulness": fmean([c["faithfulness"] for c in cases]) if cases else 0.0,
            "answer_relevancy": fmean([c["answer_relevancy"] for c in cases]) if cases else 0.0,
        },
    }


def _evaluate_ragas_groq(dataset: Any) -> Any:
    """RAGAS metrics using Groq via LangChain wrapper."""
    key = groq_api_key()
    if not key:
        raise RuntimeError("missing GROQ_API_KEY")
    model_name = groq_eval_model_name()
    from ragas import evaluate
    from ragas.llms import LangchainLLMWrapper
    from langchain_groq import ChatGroq

    groq_llm = ChatGroq(model=model_name, api_key=key, temperature=0.0)
    ragas_llm = LangchainLLMWrapper(groq_llm)

    # Prefer module-level metrics API (as requested); fallback to class API by version.
    try:
        from ragas.metrics import context_precision, context_recall, faithfulness

        faithfulness.llm = ragas_llm
        context_precision.llm = ragas_llm
        context_recall.llm = ragas_llm
        metrics = [faithfulness, context_recall, context_precision]
    except Exception:
        from ragas.metrics import ContextPrecision, ContextRecall, Faithfulness

        metrics = [
            Faithfulness(llm=ragas_llm),
            ContextRecall(llm=ragas_llm),
            ContextPrecision(llm=ragas_llm),
        ]
    return evaluate(dataset=dataset, metrics=metrics, llm=ragas_llm)


def run_ragas_eval(rows: list[EvalRuntimeRow]) -> dict[str, Any]:
    """RAGAS with Groq judge; lexical fallback if unavailable."""

    try:
        from datasets import Dataset
    except Exception as exc:
        return _lexical_fallback(rows, f"datasets import failed: {exc!s}")

    payload = {
        "question": [row.question for row in rows],
        "answer": [row.answer for row in rows],
        "contexts": [row.contexts for row in rows],
        "ground_truth": [row.expected_answer for row in rows],
    }
    dataset = Dataset.from_dict(payload)

    if not groq_api_key():
        return _lexical_fallback(
            rows,
            "GROQ_API_KEY not set. Set GROQ_API_KEY in backend/.env for RAGAS Groq judging.",
        )
    try:
        rag = _evaluate_ragas_groq(dataset)
        return _success_payload("ragas_groq", rag, rows)
    except Exception as exc:
        return _lexical_fallback(rows, f"ragas groq evaluate failed: {exc!s}")
