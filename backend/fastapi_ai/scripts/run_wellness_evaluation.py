"""Run wellness JSONL eval: plan generation + DeepEval. Loads backend/.env."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR.parent / ".env")

from wellness.evaluation.aggregate_report import run_full_evaluation


def main() -> None:
    default_dataset = ROOT_DIR / "wellness" / "evaluation" / "data" / "wellness_evalset.jsonl"
    default_output = ROOT_DIR / "tmp" / "wellness_eval_reports"
    parser = argparse.ArgumentParser(description="Weekly wellness DeepEval (see wellness/evaluation/).")
    parser.add_argument("--dataset", type=Path, default=default_dataset)
    parser.add_argument("--output-dir", type=Path, default=default_output)
    parser.add_argument("--fail-on-thresholds", action="store_true")
    parser.add_argument(
        "--judge-provider",
        default="auto",
        choices=("auto", "groq", "openai"),
        help="GEval judge LLM: auto prefers GROQ_API_KEY then OPENAI_API_KEY",
    )
    args = parser.parse_args()
    report = run_full_evaluation(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        fail_on_thresholds=args.fail_on_thresholds,
        judge_provider=args.judge_provider,
    )
    rid = report["run_id"]
    print(f"Wrote {args.output_dir / f'{rid}.json'}")
    print(f"Wrote {args.output_dir / f'{rid}.md'}")


if __name__ == "__main__":
    main()
