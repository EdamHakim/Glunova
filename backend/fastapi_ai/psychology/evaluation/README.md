# Sanadi Evaluation

This package runs offline evaluation for the psychology module with:
- RAGAS (retrieval/grounding)
- DeepEval (quality/safety)
- LLM-as-a-Judge (rubric scoring + calibration)

## Run

From `backend/fastapi_ai`:

`python scripts/run_sanadi_evaluation.py`

Optional flags:
- `--dataset <path>` custom JSONL dataset
- `--calibration <path>` custom judge calibration set
- `--output-dir <path>` report output directory
- `--strict` fail on thresholds

## Outputs

Reports are written to `backend/fastapi_ai/tmp/sanadi_eval_reports/`:
- `<run_id>.json` full machine-readable report
- `<run_id>.md` summary report
