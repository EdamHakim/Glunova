from __future__ import annotations

import json
import logging
import math
from statistics import fmean
from typing import Any

from psychology.evaluation.llm_keys import groq_api_key, groq_eval_model_name
from psychology.evaluation.runner import EvalRuntimeRow

logger = logging.getLogger(__name__)


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


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _answer_relevancy_supplement(rows: list[EvalRuntimeRow]) -> tuple[list[float], str]:
    """
    RAGAS 0.4+ AnswerRelevancy needs a separate embedding stack; we score relevancy with the same
    Groq judge as the other RAGAS LLM metrics (or lexical overlap when no key).
    """
    key = groq_api_key()
    if not key:
        return (
            [_word_overlap(r.answer, r.question) for r in rows],
            "lexical_overlap",
        )
    model_name = groq_eval_model_name()
    try:
        from groq import Groq
    except Exception as exc:
        logger.warning("groq import failed for answer relevancy: %s", exc)
        return (
            [_word_overlap(r.answer, r.question) for r in rows],
            "lexical_overlap",
        )

    client = Groq(api_key=key)
    system = (
        "You score how relevant the assistant reply is to the patient question for a "
        "diabetes mental-health coach. Ignore JSON formatting in the reply. "
        'Return only a JSON object: {"score": <number between 0 and 1>} where 1 means fully on-topic.'
    )
    scores: list[float] = []
    for row in rows:
        try:
            response = client.chat.completions.create(
                model=model_name,
                temperature=0.0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": f"Question:\n{row.question[:2400]}\n\nAnswer:\n{row.answer[:2400]}",
                    },
                ],
            )
            raw = (response.choices[0].message.content or "{}").strip()
            if "```" in raw:
                raw = (
                    raw.split("```json", 1)[-1].split("```", 1)[0].strip()
                    if "```json" in raw
                    else raw.split("```", 1)[1].split("```", 1)[0].strip()
                )
            payload = json.loads(raw)
            sc = payload.get("score")
            scores.append(_clamp01(_safe_float(sc)))
        except Exception as exc:
            logger.debug("answer relevancy groq row failed: %s", exc, exc_info=True)
            scores.append(_word_overlap(row.answer, row.question))
    return scores, "groq_json"


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
        "answer_relevancy_engine": "lexical_overlap",
        "cases": fallback_cases,
        "aggregate": {
            "context_precision": fmean([c["context_precision"] for c in fallback_cases]) if fallback_cases else 0.0,
            "context_recall": fmean([c["context_recall"] for c in fallback_cases]) if fallback_cases else 0.0,
            "faithfulness": fmean([c["faithfulness"] for c in fallback_cases]) if fallback_cases else 0.0,
            "answer_relevancy": fmean([c["answer_relevancy"] for c in fallback_cases]) if fallback_cases else 0.0,
        },
    }


def _cases_from_result(
    ragas_result: Any,
    rows: list[EvalRuntimeRow],
    answer_relevancy_scores: list[float],
) -> list[dict[str, Any]]:
    table = ragas_result.to_pandas().to_dict(orient="records")
    cases = []
    for idx, row in enumerate(rows):
        item = table[idx] if idx < len(table) else {}
        ar = (
            answer_relevancy_scores[idx]
            if idx < len(answer_relevancy_scores)
            else _word_overlap(row.answer, row.question)
        )
        cases.append(
            {
                "sample_id": row.sample_id,
                "context_precision": _safe_float(item.get("context_precision", 0.0)),
                "context_recall": _safe_float(item.get("context_recall", 0.0)),
                "faithfulness": _safe_float(item.get("faithfulness", 0.0)),
                "answer_relevancy": _clamp01(_safe_float(ar)),
            }
        )
    return cases


def _success_payload(
    engine: str,
    ragas_result: Any,
    rows: list[EvalRuntimeRow],
    answer_relevancy_scores: list[float],
    answer_relevancy_engine: str,
) -> dict[str, Any]:
    cases = _cases_from_result(ragas_result, rows, answer_relevancy_scores)
    return {
        "engine": engine,
        "fallback_reason": None,
        "answer_relevancy_engine": answer_relevancy_engine,
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
    from ragas.run_config import RunConfig
    from langchain_groq import ChatGroq

    groq_llm = ChatGroq(model=model_name, api_key=key, temperature=0.0)
    ragas_llm = LangchainLLMWrapper(groq_llm)
    # Default RunConfig(timeout=180, max_workers=16) causes TimeoutError when many faithfulness /
    # context jobs pile up behind Groq rate limits; give each job more time and ease concurrency.
    run_config = RunConfig(timeout=600, max_workers=6, max_retries=12)

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
    return evaluate(dataset=dataset, metrics=metrics, llm=ragas_llm, run_config=run_config)


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
    ar_scores, ar_engine = _answer_relevancy_supplement(rows)
    try:
        rag = _evaluate_ragas_groq(dataset)
        return _success_payload("ragas_groq", rag, rows, ar_scores, ar_engine)
    except Exception as exc:
        return _lexical_fallback(rows, f"ragas groq evaluate failed: {exc!s}")
