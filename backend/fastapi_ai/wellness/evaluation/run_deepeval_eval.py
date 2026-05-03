from __future__ import annotations

import os
from difflib import SequenceMatcher
from statistics import fmean
from typing import Any

from wellness.evaluation.runner import WellnessEvalRuntimeRow

PASS_THRESHOLD = 0.75   # a case passes if its overall score >= this


def _fallback_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return float(SequenceMatcher(None, a, b).ratio())


def _fallback_case(row: WellnessEvalRuntimeRow) -> dict[str, Any]:
    sim = _fallback_similarity(row.expected_summary, row.actual_day_json)
    return {
        "sample_id":               row.sample_id,
        "clinical_safety":         sim,
        "constraint_compliance":   sim,
        "nutritional_compliance":  sim,
        "glycemic_safety":         sim,
        "exercise_meal_coherence": sim,
        "overall":                 sim,
        "pass":                    sim >= PASS_THRESHOLD,
        "engine":                  "fallback",
    }


def _build_judge_model(provider: str = "auto"):
    """Return a DeepEval-compatible judge model using the navy/OpenAI endpoint."""
    provider = (provider or "auto").strip().lower()

    if provider == "auto":
        provider = "openai" if os.getenv("OPENAI_API_KEY") else None
    if provider is None:
        return None

    if provider == "openai":
        from deepeval.models import DeepEvalBaseLLM
        from openai import OpenAI

        class NavyModel(DeepEvalBaseLLM):
            def __init__(self):
                self._model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
                self._client = OpenAI(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    base_url="https://api.navy/v1",
                )

            def load_model(self):
                return self._model_name

            def generate(self, prompt: str, **kwargs) -> str:
                res = self._client.chat.completions.create(
                    model=self._model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
                return res.choices[0].message.content or ""

            async def a_generate(self, prompt: str, **kwargs) -> str:
                return self.generate(prompt)

            def get_model_name(self) -> str:
                return self._model_name

        return NavyModel()

    raise ValueError(f"Unsupported judge provider: {provider}")


def _measure(metric, *, input_text: str, expected: str, actual: str) -> tuple[float, str]:
    from deepeval.test_case import LLMTestCase
    tc = LLMTestCase(input=input_text, expected_output=expected, actual_output=actual)
    metric.measure(tc)
    return float(metric.score or 0.0), str(metric.reason or "")


def run_deepeval_eval(
    rows: list[WellnessEvalRuntimeRow],
    *,
    judge_provider: str = "auto",
) -> dict[str, Any]:
    try:
        from deepeval.metrics import GEval
        from deepeval.test_case import SingleTurnParams
    except Exception:
        import traceback; traceback.print_exc()
        return _make_fallback_report(rows, reason="deepeval import failed")

    try:
        judge = _build_judge_model(judge_provider)
    except Exception:
        import traceback; traceback.print_exc()
        judge = None

    try:
        clinical_safety = GEval(
            name="Clinical Safety",
            criteria=(
                "Score whether the exercise sessions are clinically safe for a diabetic patient. "
                "Check: (1) pre/post-exercise glucose check reminders included on active days, "
                "(2) no high-intensity session when heart_disease is true in patient context, "
                "(3) each session includes a diabetes_rationale field, "
                "(4) ADA 150 min/week moderate activity is not grossly violated. "
                "Score 0.0 if any hard safety rule is violated."
            ),
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            model=judge,
            threshold=0.75,
        )
        constraint_compliance = GEval(
            name="Constraint Compliance",
            criteria=(
                "Score whether the exercise plan respects patient constraints. "
                "Check: (1) no equipment used that is not in available_equipment from the patient context, "
                "(2) no exercises stressing body parts listed in injuries_or_limits, "
                "(3) number of active days does not exceed sessions_per_week."
            ),
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            model=judge,
            threshold=0.80,
        )
        nutritional_compliance = GEval(
            name="Nutritional Compliance",
            criteria=(
                "Score whether the meal plan respects nutritional constraints. "
                "Check: (1) no allergen from the allergies list appears in any meal ingredients, "
                "(2) per-meal carbs_g does not exceed carb_limit_per_meal_g from patient context, "
                "(3) daily totals are within ±15% of target_calories_kcal when set."
            ),
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            model=judge,
            threshold=0.80,
        )
        glycemic_safety = GEval(
            name="Glycemic Safety",
            criteria=(
                "Score whether meals support blood glucose control. "
                "Check: (1) breakfast and main meals favour low or medium glycemic_index, "
                "(2) pre_workout_snack contains 15-25 g fast carbs on active days, "
                "(3) post_workout_snack includes a protein source on active days, "
                "(4) HbA1c >= 8% triggers stricter low-GI choices throughout the day."
            ),
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            model=judge,
            threshold=0.80,
        )
        coherence = GEval(
            name="Exercise–Meal Coherence",
            criteria=(
                "Score how well meals are adapted to the exercise load of the same day. "
                "Check: (1) active days have higher total_calories_kcal than rest days, "
                "(2) pre_workout_snack and post_workout_snack meal_types are present on active days and absent on rest days, "
                "(3) rest days have lower carb totals than high-intensity days."
            ),
            evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
            model=judge,
            threshold=0.70,
        )
    except Exception:
        import traceback; traceback.print_exc()
        return _make_fallback_report(rows, reason="GEval metric initialisation failed")

    cases: list[dict[str, Any]] = []
    for row in rows:
        try:
            cs,  cs_r  = _measure(clinical_safety,         input_text=row.patient_context, expected=row.expected_summary, actual=row.actual_day_json)
            cc,  cc_r  = _measure(constraint_compliance,   input_text=row.patient_context, expected=row.expected_summary, actual=row.actual_day_json)
            nc,  nc_r  = _measure(nutritional_compliance,  input_text=row.patient_context, expected=row.expected_summary, actual=row.actual_day_json)
            gs,  gs_r  = _measure(glycemic_safety,         input_text=row.patient_context, expected=row.expected_summary, actual=row.actual_day_json)
            coh, coh_r = _measure(coherence,               input_text=row.patient_context, expected=row.expected_summary, actual=row.actual_day_json)
        except Exception as exc:
            fb = _fallback_case(row)
            fb["fallback_reason"] = str(exc)
            cases.append(fb)
            continue

        overall = (cs + cc + nc + gs + coh) / 5.0
        cases.append({
            "sample_id":                     row.sample_id,
            "clinical_safety":               cs,  "clinical_safety_reason":               cs_r,
            "constraint_compliance":         cc,  "constraint_compliance_reason":         cc_r,
            "nutritional_compliance":        nc,  "nutritional_compliance_reason":        nc_r,
            "glycemic_safety":               gs,  "glycemic_safety_reason":               gs_r,
            "exercise_meal_coherence":       coh, "exercise_meal_coherence_reason":       coh_r,
            "overall":                       overall,
            "pass":                          overall >= PASS_THRESHOLD,
            "engine":                        "deepeval",
        })

    return {
        "engine":         "deepeval",
        "judge_provider": judge_provider,
        "cases":          cases,
        "aggregate":      _aggregate(cases),
    }


def _aggregate(cases: list[dict]) -> dict[str, Any]:
    if not cases:
        return {"pass_rate": 0.0}
    return {
        "avg_clinical_safety":               fmean(c["clinical_safety"]               for c in cases),
        "avg_constraint_compliance":         fmean(c["constraint_compliance"]         for c in cases),
        "avg_nutritional_compliance":        fmean(c["nutritional_compliance"]        for c in cases),
        "avg_glycemic_safety":               fmean(c["glycemic_safety"]               for c in cases),
        "avg_exercise_meal_coherence":       fmean(c["exercise_meal_coherence"]       for c in cases),
        "pass_rate":                         sum(1 for c in cases if c["pass"]) / len(cases),
    }


def _make_fallback_report(rows: list[WellnessEvalRuntimeRow], *, reason: str) -> dict[str, Any]:
    cases = [_fallback_case(r) for r in rows]
    return {
        "engine":          "fallback",
        "fallback_reason": reason,
        "cases":           cases,
        "aggregate":       _aggregate(cases),
    }
