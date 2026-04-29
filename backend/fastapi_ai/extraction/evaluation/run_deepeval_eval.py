from __future__ import annotations

import json
import os
from difflib import SequenceMatcher
from statistics import fmean
from typing import Any

from extraction.evaluation.runner import OcrEvalRuntimeRow


def _json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _fallback_similarity(expected: str, actual: str) -> float:
    if not expected and not actual:
        return 1.0
    return float(SequenceMatcher(None, expected, actual).ratio())


def _fallback_case(row: OcrEvalRuntimeRow) -> dict[str, Any]:
    expected_ocr = row.expected_ocr_text or ""
    expected_json_text = _json_text(row.expected_extracted_json)
    actual_json_text = _json_text(row.actual_extracted_json)
    ocr_score = _fallback_similarity(expected_ocr, row.actual_ocr_text) if expected_ocr else 0.0
    extraction_score = _fallback_similarity(expected_json_text, actual_json_text)
    doc_type_score = 1.0
    if row.expected_document_type:
        doc_type_score = 1.0 if row.actual_extracted_json.get("document_type") == row.expected_document_type else 0.0
    groundedness = 1.0 if not row.review_required else 0.6
    overall = (ocr_score + extraction_score + doc_type_score + groundedness) / 4.0
    return {
        "sample_id": row.sample_id,
        "ocr_fidelity": ocr_score,
        "structured_correctness": extraction_score,
        "document_type_correct": doc_type_score,
        "groundedness": groundedness,
        "overall": overall,
        "pass": overall >= 0.7,
        "engine": "fallback",
    }


def _measure_geval(metric, *, input_text: str, expected_text: str, actual_text: str) -> tuple[float, str]:
    from deepeval.test_case import LLMTestCase

    test_case = LLMTestCase(input=input_text, expected_output=expected_text, actual_output=actual_text)
    metric.measure(test_case)
    return float(metric.score or 0.0), str(metric.reason or "")


def _build_judge_model(provider: str, model_name: str | None):
    provider = (provider or "auto").strip().lower()
    if provider == "auto":
        if os.getenv("GROQ_API_KEY"):
            provider = "groq"
        elif os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
            provider = "gemini"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        else:
            return None

    if provider == "groq":
        from deepeval.models import DeepEvalBaseLLM
        import groq

        class GroqModel(DeepEvalBaseLLM):
            def __init__(self, model_name="llama-3.3-70b-versatile"):
                self.model_name = model_name
                self.sync_client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
                self.async_client = groq.AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

            def load_model(self):
                return self.model_name

            def generate(self, prompt: str, **kwargs) -> str:
                res = self.sync_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model_name,
                    temperature=0
                )
                return res.choices[0].message.content or ""

            async def a_generate(self, prompt: str, **kwargs) -> str:
                res = await self.async_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model_name,
                    temperature=0
                )
                return res.choices[0].message.content or ""

            def get_model_name(self):
                return self.model_name

        return GroqModel(model_name=model_name or os.getenv("DEEPEVAL_GROQ_MODEL") or "llama-3.3-70b-versatile")

    if provider == "gemini":
        from deepeval.models import GeminiModel

        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        return GeminiModel(
            model=model_name or os.getenv("DEEPEVAL_GEMINI_MODEL") or "gemini-2.0-flash",
            api_key=api_key,
            temperature=0,
        )

    if provider == "openai":
        from deepeval.models import GPTModel

        return GPTModel(
            model=model_name or os.getenv("DEEPEVAL_OPENAI_MODEL") or "gpt-4.1",
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0,
        )

    if provider == "litellm":
        from deepeval.models import LiteLLMModel

        return LiteLLMModel(
            model=model_name or os.getenv("DEEPEVAL_LITELLM_MODEL"),
            api_key=os.getenv("LITELLM_API_KEY"),
            base_url=os.getenv("LITELLM_BASE_URL"),
            temperature=0,
        )

    raise ValueError("judge provider must be one of: auto, gemini, openai, litellm")


def run_deepeval_eval(
    rows: list[OcrEvalRuntimeRow],
    *,
    judge_provider: str = "auto",
    judge_model: str | None = None,
) -> dict[str, Any]:
    try:
        from deepeval.metrics import GEval
        from deepeval.test_case import SingleTurnParams
    except Exception as e:
        import traceback
        traceback.print_exc()
        cases = [_fallback_case(row) for row in rows]
        return {
            "engine": "fallback",
            "cases": cases,
            "aggregate": {
                "avg_ocr_fidelity": fmean([c["ocr_fidelity"] for c in cases]) if cases else 0.0,
                "avg_structured_correctness": fmean([c["structured_correctness"] for c in cases]) if cases else 0.0,
                "avg_document_type_correct": fmean([c["document_type_correct"] for c in cases]) if cases else 0.0,
                "avg_groundedness": fmean([c["groundedness"] for c in cases]) if cases else 0.0,
                "pass_rate": (sum(1 for c in cases if c["pass"]) / len(cases)) if cases else 0.0,
            },
        }

    try:
        judge_model_instance = _build_judge_model(judge_provider, judge_model)
    except Exception as e:
        import traceback
        traceback.print_exc()
        judge_model_instance = None

    try:
        ocr_metric = GEval(
            name="OCR Fidelity",
            criteria="Score whether the OCR transcript preserves the clinically relevant text from the reference transcript without dropping or hallucinating medical facts.",
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
            ],
            model=judge_model_instance,
            threshold=0.7,
        )
        extraction_metric = GEval(
            name="Structured Extraction Correctness",
            criteria="Score whether the extracted JSON captures the expected medical fields, values, units, and document type with minimal omissions or wrong assignments.",
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
            ],
            model=judge_model_instance,
            threshold=0.7,
        )
        grounding_metric = GEval(
            name="Extraction Groundedness",
            criteria="Score whether the extracted medical fields appear well grounded in the OCR transcript and do not introduce unsupported facts.",
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
            ],
            model=judge_model_instance,
            threshold=0.7,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        cases = [_fallback_case(row) for row in rows]
        return {
            "engine": "fallback",
            "cases": cases,
            "aggregate": {
                "avg_ocr_fidelity": fmean([c["ocr_fidelity"] for c in cases]) if cases else 0.0,
                "avg_structured_correctness": fmean([c["structured_correctness"] for c in cases]) if cases else 0.0,
                "avg_document_type_correct": fmean([c["document_type_correct"] for c in cases]) if cases else 0.0,
                "avg_groundedness": fmean([c["groundedness"] for c in cases]) if cases else 0.0,
                "pass_rate": (sum(1 for c in cases if c["pass"]) / len(cases)) if cases else 0.0,
            },
        }

    cases: list[dict[str, Any]] = []
    for row in rows:
        expected_json_text = _json_text(row.expected_extracted_json)
        actual_json_text = _json_text(row.actual_extracted_json)
        expected_ocr = row.expected_ocr_text or ""

        if expected_ocr:
            ocr_score, ocr_reason = _measure_geval(
                ocr_metric,
                input_text=f"OCR evaluation for sample {row.sample_id}",
                expected_text=expected_ocr,
                actual_text=row.actual_ocr_text,
            )
        else:
            ocr_score, ocr_reason = 0.0, "No expected OCR transcript provided."

        extraction_score, extraction_reason = _measure_geval(
            extraction_metric,
            input_text=f"Structured extraction evaluation for sample {row.sample_id}. OCR transcript:\n{row.actual_ocr_text}",
            expected_text=expected_json_text,
            actual_text=actual_json_text,
        )
        grounding_score, grounding_reason = _measure_geval(
            grounding_metric,
            input_text=f"OCR transcript:\n{row.actual_ocr_text}",
            expected_text="",
            actual_text=actual_json_text,
        )

        doc_type_score = 1.0
        if row.expected_document_type:
            doc_type_score = 1.0 if row.actual_extracted_json.get("document_type") == row.expected_document_type else 0.0

        overall = (ocr_score + extraction_score + grounding_score + doc_type_score) / 4.0
        cases.append(
            {
                "sample_id": row.sample_id,
                "ocr_fidelity": ocr_score,
                "ocr_reason": ocr_reason,
                "structured_correctness": extraction_score,
                "structured_reason": extraction_reason,
                "groundedness": grounding_score,
                "groundedness_reason": grounding_reason,
                "document_type_correct": doc_type_score,
                "overall": overall,
                "pass": overall >= 0.7,
                "engine": "deepeval",
            }
        )

    return {
        "engine": "deepeval",
        "judge_provider": judge_provider,
        "judge_model": getattr(judge_model_instance, "model", None) or getattr(judge_model_instance, "name", None),
        "cases": cases,
        "aggregate": {
            "avg_ocr_fidelity": fmean([c["ocr_fidelity"] for c in cases]) if cases else 0.0,
            "avg_structured_correctness": fmean([c["structured_correctness"] for c in cases]) if cases else 0.0,
            "avg_document_type_correct": fmean([c["document_type_correct"] for c in cases]) if cases else 0.0,
            "avg_groundedness": fmean([c["groundedness"] for c in cases]) if cases else 0.0,
            "pass_rate": (sum(1 for c in cases if c["pass"]) / len(cases)) if cases else 0.0,
        },
    }
