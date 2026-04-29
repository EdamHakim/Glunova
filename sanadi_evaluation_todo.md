# Sanadi Evaluation TODO

## Milestone 1 - Foundation
- [x] Define evaluation scope (RAGAS + DeepEval + LLM-as-a-Judge).
- [x] Add evaluation dependencies in `backend/fastapi_ai/requirements.txt`.
- [x] Scaffold `backend/fastapi_ai/psychology/evaluation/` package.
- [x] Add runnable orchestration script in `backend/fastapi_ai/scripts/`.

## Milestone 2 - Dataset and Runner
- [x] Define dataset schema for Sanadi evaluation samples.
- [x] Create baseline dataset JSONL fixture.
- [x] Implement pipeline runner that collects answer + retrieved context.

## Milestone 3 - Scoring
- [x] Implement RAGAS retrieval/grounding scoring.
- [x] Implement DeepEval relevance and safety checks.
- [x] Implement LLM-as-a-Judge rubric scoring.
- [x] Add calibration set and calibration report logic.

## Milestone 4 - Reporting and Ops
- [x] Aggregate per-case and global metrics into a single report.
- [x] Emit timestamped JSON and markdown summaries.
- [x] Document one-command local execution steps.
- [x] Add optional strict mode threshold checks for CI usage.

## Completion Criteria
- [x] A single command runs full evaluation end-to-end.
- [x] Report includes RAGAS + DeepEval + LLM judge sections.
- [x] Baseline dataset is committed for repeatable runs.
