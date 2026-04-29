from __future__ import annotations

from statistics import fmean
from typing import Any

from psychology.evaluation.llm_keys import gemini_eval_model_name, google_api_key, openai_api_key
from psychology.evaluation.runner import EvalRuntimeRow


def _word_overlap(a: str, b: str) -> float:
    a_set = {tok for tok in a.lower().split() if tok}
    b_set = {tok for tok in b.lower().split() if tok}
    if not a_set:
        return 0.0
    return len(a_set.intersection(b_set)) / len(a_set)


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
                "context_precision": float(item.get("context_precision", 0.0) or 0.0),
                "context_recall": float(item.get("context_recall", 0.0) or 0.0),
                "faithfulness": float(item.get("faithfulness", 0.0) or 0.0),
                "answer_relevancy": float(item.get("answer_relevancy", 0.0) or 0.0),
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


def _evaluate_ragas_gemini(dataset: Any) -> Any:
    """RAGAS metrics using Gemini (google-genai or OpenAI-compatible Gemini endpoint)."""
    key = google_api_key()
    if not key:
        raise RuntimeError("missing GOOGLE_API_KEY")
    model_name = gemini_eval_model_name()
    from ragas import evaluate

    llm = None

    try:
        from google import genai
        from ragas.llms import llm_factory

        llm = llm_factory(model_name, provider="google", client=genai.Client(api_key=key))
    except Exception:
        llm = None

    if llm is None:
        from openai import OpenAI
        from ragas.llms import llm_factory

        llm = llm_factory(
            model_name,
            provider="openai",
            client=OpenAI(
                api_key=key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            ),
        )

    from ragas.metrics import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness

    metrics = [
        ContextPrecision(llm=llm),
        ContextRecall(llm=llm),
        Faithfulness(llm=llm),
        AnswerRelevancy(llm=llm),
    ]
    return evaluate(dataset=dataset, metrics=metrics)


def run_ragas_eval(rows: list[EvalRuntimeRow]) -> dict[str, Any]:
    """RAGAS: prefer Gemini (GOOGLE_API_KEY), then OpenAI, else lexical overlap."""

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

    gemini_error: str | None = None
    if google_api_key():
        try:
            rag = _evaluate_ragas_gemini(dataset)
            return _success_payload("ragas_gemini", rag, rows)
        except Exception as exc:
            gemini_error = repr(exc)

    if openai_api_key():
        try:
            from ragas import evaluate
            from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

            ragas_result = evaluate(
                dataset=dataset,
                metrics=[context_precision, context_recall, faithfulness, answer_relevancy],
            )
            return _success_payload("ragas_openai", ragas_result, rows)
        except Exception as exc:
            suffix = f" Gemini error was: {gemini_error}" if gemini_error else ""
            return _lexical_fallback(rows, f"ragas evaluate failed: {exc!s}.{suffix}")

    msg = (
        "No GOOGLE_API_KEY / GEMINI_API_KEY or OPENAI_API_KEY — RAGAS LLM metrics skipped. "
        "Add your Gemini key from AI Studio as GOOGLE_API_KEY in backend/.env (no OpenAI needed). "
        "Install: pip install google-genai ragas (upgrade ragas if llm_factory is missing)."
    )
    if gemini_error:
        msg += f" Last Gemini attempt: {gemini_error}"
    return _lexical_fallback(rows, msg)
