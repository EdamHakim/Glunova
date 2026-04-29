from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from extraction.evaluation.run_deepeval_eval import run_deepeval_eval
from extraction.evaluation.runner import build_runtime_rows_sync


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OCR + extraction evaluation with DeepEval / LLM-as-a-Judge.")
    parser.add_argument("--dataset", required=True, help="Path to JSONL evaluation dataset.")
    parser.add_argument(
        "--ocr-backend",
        default="auto",
        choices=["auto", "azure", "local"],
        help="OCR backend to evaluate.",
    )
    parser.add_argument(
        "--output",
        default="tmp/extraction_eval_report.json",
        help="Where to write the machine-readable report.",
    )
    parser.add_argument(
        "--judge-provider",
        default="auto",
        choices=["auto", "gemini", "openai", "litellm"],
        help="Which judge backend DeepEval should use.",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="Optional judge model name override, for example gemini-1.5-pro.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset).resolve()
    output_path = Path(args.output).resolve()
    rows = build_runtime_rows_sync(dataset_path, ocr_backend=args.ocr_backend)
    report = run_deepeval_eval(rows, judge_provider=args.judge_provider, judge_model=args.judge_model)
    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset_path),
        "ocr_backend": args.ocr_backend,
        "judge_provider": args.judge_provider,
        "judge_model": args.judge_model,
        "samples": len(rows),
        "report": report,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["report"]["aggregate"], ensure_ascii=False, indent=2))
    print(f"Saved report to {output_path}")


if __name__ == "__main__":
    main()
