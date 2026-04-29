from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psychology.evaluation.dataset_schema import load_eval_samples
from psychology.evaluation.run_deepeval_eval import run_deepeval_eval
from psychology.evaluation.run_llm_judge_eval import run_judge_calibration, run_llm_judge_eval
from psychology.evaluation.run_ragas_eval import run_ragas_eval
from psychology.evaluation.runner import run_samples


def _build_markdown_summary(report: dict[str, Any]) -> str:
    ragas_raw = report.get("ragas") or {}
    ragas = ragas_raw.get("aggregate") or {}
    ragas_engine = ragas_raw.get("engine", "?")
    ragas_note = ragas_raw.get("fallback_reason")
    deepeval_raw = report.get("deepeval") or {}
    deepeval = deepeval_raw.get("aggregate") or {}
    deepeval_engine = deepeval_raw.get("engine", "?")
    deepeval_note = deepeval_raw.get("fallback_reason")
    judge = report["llm_judge"]["aggregate"]
    calibration = report["judge_calibration"]
    lines = [
            "# Sanadi Evaluation Report",
            "",
            f"- Run id: `{report['run_id']}`",
            f"- Generated at: `{report['generated_at']}`",
            f"- Cases: `{report['dataset_size']}`",
            "",
            "## RAGAS",
            f"- Engine: `{ragas_engine}`",
    ]
    if ragas_note:
        lines.append(f"- Note: {ragas_note}")
    lines.extend(
        [
            f"- Context precision: `{ragas.get('context_precision', 0.0):.3f}`",
            f"- Context recall: `{ragas.get('context_recall', 0.0):.3f}`",
            f"- Faithfulness: `{ragas.get('faithfulness', 0.0):.3f}`",
            f"- Answer relevancy: `{ragas.get('answer_relevancy', 0.0):.3f}`",
            "",
            "## DeepEval",
            f"- Engine: `{deepeval_engine}`",
        ]
    )
    if deepeval_note:
        lines.append(f"- Note: {deepeval_note}")
    lines.extend(
        [
            f"- Avg answer relevancy: `{deepeval.get('avg_answer_relevancy', 0.0):.3f}`",
            f"- Avg safety score: `{deepeval.get('avg_safety_score', 0.0):.3f}`",
            f"- Pass rate: `{deepeval.get('pass_rate', 0.0):.3f}`",
            "",
            "## LLM Judge",
            f"- Overall score: `{judge.get('overall_score', 0.0):.3f}`",
            f"- Avg empathy: `{judge.get('avg_empathy', 0.0):.3f}`",
            f"- Avg non diagnostic language: `{judge.get('avg_non_diagnostic_language', 0.0):.3f}`",
            f"- Avg escalation correctness: `{judge.get('avg_escalation_correctness', 0.0):.3f}`",
            f"- Calibration critical pass rate: `{float(calibration.get('critical_pass_rate', 0.0)):.3f}`",
            "",
        ]
    )
    return "\n".join(lines)


def run_full_evaluation(
    dataset_path: Path,
    output_dir: Path,
    calibration_path: Path | None = None,
    fail_on_thresholds: bool = False,
) -> dict[str, Any]:
    samples = load_eval_samples(dataset_path)
    runtime_rows = run_samples(samples)
    ragas_report = run_ragas_eval(runtime_rows)
    deepeval_report = run_deepeval_eval(runtime_rows)
    llm_judge_report = run_llm_judge_eval(runtime_rows)
    calibration = (
        run_judge_calibration(calibration_path)
        if calibration_path is not None
        else {"cases": 0, "critical_pass_rate": 0.0, "notes": "not provided"}
    )

    run_id = datetime.now(timezone.utc).strftime("sanadi_eval_%Y%m%dT%H%M%SZ")
    report = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_size": len(samples),
        "dataset_path": str(dataset_path),
        "runtime_rows": [row.to_dict() for row in runtime_rows],
        "ragas": ragas_report,
        "deepeval": deepeval_report,
        "llm_judge": llm_judge_report,
        "judge_calibration": calibration,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{run_id}.json"
    md_path = output_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_build_markdown_summary(report), encoding="utf-8")
    report["json_report_path"] = str(json_path)
    report["markdown_report_path"] = str(md_path)

    if fail_on_thresholds:
        if float(deepeval_report["aggregate"]["pass_rate"]) < 0.6:
            raise RuntimeError("DeepEval pass_rate below threshold 0.60")
        if float(llm_judge_report["aggregate"]["overall_score"]) < 3.0:
            raise RuntimeError("LLM judge overall score below threshold 3.0")
        if float(calibration["critical_pass_rate"]) < 1.0:
            raise RuntimeError("Judge calibration critical_pass_rate below threshold 1.0")
    return report

