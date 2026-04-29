# Sanadi Evaluation

This package runs offline evaluation for the psychology module with:
- RAGAS (retrieval/grounding)
- DeepEval (quality/safety)

## Run

From `backend/fastapi_ai`:

`python scripts/run_sanadi_evaluation.py`

### Evaluator key and model

- Set `GROQ_API_KEY` in `backend/.env`.
- Optional model override:
  - `SANADI_EVAL_GROQ_MODEL` (default `llama-3.3-70b-versatile`)

Both RAGAS and DeepEval judges use Groq in the current implementation.

Optional flags:
- `--dataset <path>` custom JSONL dataset
- `--output-dir <path>` report output directory
- `--strict` fail on thresholds

## Outputs

Reports are written to `backend/fastapi_ai/tmp/sanadi_eval_reports/`:
- `<run_id>.json` full machine-readable report
- `<run_id>.md` summary report
