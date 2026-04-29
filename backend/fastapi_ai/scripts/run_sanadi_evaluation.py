#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

_FASTAPI_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _FASTAPI_ROOT.parent

if str(_FASTAPI_ROOT) not in sys.path:
    sys.path.insert(0, str(_FASTAPI_ROOT))

load_dotenv(_BACKEND_ROOT / ".env", override=True)

from psychology.evaluation.aggregate_report import run_full_evaluation
from psychology.evaluation.build_eval_dataset import build_default_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Sanadi psychology evaluation stack")
    parser.add_argument(
        "--dataset",
        default="",
        help="Path to evaluation JSONL dataset (default: backend/fastapi_ai/psychology/evaluation/data/sanadi_evalset.jsonl)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_FASTAPI_ROOT / "tmp" / "sanadi_eval_reports"),
        help="Directory where JSON/markdown reports are written",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail with non-zero code if configured thresholds are not met",
    )
    parser.add_argument(
        "--calibration",
        default="",
        help="Path to LLM judge calibration JSONL (default: built-in calibration file)",
    )
    args = parser.parse_args()

    if args.dataset:
        dataset_path = Path(args.dataset)
    else:
        dataset_path = _FASTAPI_ROOT / "psychology" / "evaluation" / "data" / "sanadi_evalset.jsonl"
    calibration_path = (
        Path(args.calibration)
        if args.calibration
        else _FASTAPI_ROOT / "psychology" / "evaluation" / "data" / "llm_judge_calibration.jsonl"
    )

    if not dataset_path.exists():
        build_default_dataset(dataset_path)

    report = run_full_evaluation(
        dataset_path=dataset_path,
        output_dir=Path(args.output_dir),
        calibration_path=calibration_path,
        fail_on_thresholds=bool(args.strict),
    )
    print(json.dumps({"run_id": report["run_id"], "json_report_path": report["json_report_path"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

