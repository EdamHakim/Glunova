from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wellness.evaluation.dataset_schema import WellnessEvalSample
from wellness.evaluation.run_deepeval_eval import run_deepeval_eval
from wellness.evaluation.runner import WellnessEvalRuntimeRow, build_runtime_rows, load_eval_samples

_BACKEND_ENV = Path(__file__).resolve().parents[3] / ".env"


def _load_backend_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    if _BACKEND_ENV.is_file():
        load_dotenv(_BACKEND_ENV, override=False)


_DEFAULT_DATASET = Path(__file__).parent / "data" / "wellness_evalset.jsonl"
_DEFAULT_OUTPUT  = Path(__file__).parent.parent.parent.parent / "tmp" / "wellness_eval_reports"


def _markdown_summary(report: dict[str, Any]) -> str:
    agg = report.get("deepeval", {}).get("aggregate", {})
    lines = [
        f"# Wellness Evaluation — {report['run_id']}",
        f"Generated: {report['generated_at']}  |  Dataset size: {report['dataset_size']}",
        "",
        "## DeepEval Aggregate",
        f"| Metric | Score |",
        f"|--------|-------|",
        f"| Clinical Safety          | {agg.get('avg_clinical_safety', 0):.2f} |",
        f"| Constraint Compliance    | {agg.get('avg_constraint_compliance', 0):.2f} |",
        f"| Nutritional Compliance   | {agg.get('avg_nutritional_compliance', 0):.2f} |",
        f"| Glycemic Safety          | {agg.get('avg_glycemic_safety', 0):.2f} |",
        f"| Exercise–Meal Coherence  | {agg.get('avg_exercise_meal_coherence', 0):.2f} |",
        f"| **Pass Rate**            | **{agg.get('pass_rate', 0):.0%}** |",
    ]
    return "\n".join(lines)


def run_full_evaluation(
    dataset_path: Path = _DEFAULT_DATASET,
    output_dir:   Path = _DEFAULT_OUTPUT,
    *,
    fail_on_thresholds: bool = False,
) -> dict[str, Any]:
    _load_backend_dotenv()
    samples:      list[WellnessEvalSample]     = load_eval_samples(dataset_path)
    runtime_rows: list[WellnessEvalRuntimeRow] = build_runtime_rows(samples)
    deepeval_report = run_deepeval_eval(runtime_rows)

    run_id = datetime.now(timezone.utc).strftime("wellness_eval_%Y%m%dT%H%M%SZ")
    report: dict[str, Any] = {
        "run_id":        run_id,
        "generated_at":  datetime.now(timezone.utc).isoformat(),
        "dataset_size":  len(samples),
        "dataset_path":  str(dataset_path),
        "runtime_rows":  [r.to_dict() for r in runtime_rows],
        "deepeval":      deepeval_report,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{run_id}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / f"{run_id}.md").write_text(
        _markdown_summary(report), encoding="utf-8"
    )

    if fail_on_thresholds:
        pass_rate = float(deepeval_report.get("aggregate", {}).get("pass_rate", 0))
        if pass_rate < 0.75:
            raise RuntimeError(f"DeepEval pass_rate {pass_rate:.0%} is below the 75% threshold")

    return report


if __name__ == "__main__":
    run_full_evaluation(fail_on_thresholds=False)
