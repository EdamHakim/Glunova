from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from wellness.evaluation.dataset_schema import WellnessEvalSample
from wellness.weekly_wellness_pipeline import generate_weekly_wellness_plan
from wellness.weekly_wellness_schema import WeeklyWellnessPlanRequest


@dataclass(slots=True)
class WellnessEvalRuntimeRow:
    sample_id:        str
    patient_context:  str   # raw JSON string — used as LLMTestCase INPUT
    day_index:        int
    actual_day_json:  str   # serialized generated day — used as ACTUAL_OUTPUT
    expected_summary: str   # used as EXPECTED_OUTPUT
    tags:             list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_eval_samples(dataset_path: Path) -> list[WellnessEvalSample]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    samples: list[WellnessEvalSample] = []
    for idx, line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {idx}: {exc}") from exc
        samples.append(WellnessEvalSample(**payload))
    return samples


def build_runtime_rows(samples: list[WellnessEvalSample]) -> list[WellnessEvalRuntimeRow]:
    rows: list[WellnessEvalRuntimeRow] = []
    for sample in samples:
        ctx = json.loads(sample.patient_context)
        # Force single-day generation so we only pay for what we evaluate
        ctx["day_index"] = sample.day_index
        req = WeeklyWellnessPlanRequest(**ctx)

        plan = generate_weekly_wellness_plan(req)
        days = plan.get("days", [])
        day_obj = next((d for d in days if d.get("day_index") == sample.day_index), days[0] if days else {})

        rows.append(WellnessEvalRuntimeRow(
            sample_id=sample.sample_id,
            patient_context=sample.patient_context,
            day_index=sample.day_index,
            actual_day_json=json.dumps(day_obj, ensure_ascii=False),
            expected_summary=sample.expected_day_summary,
            tags=sample.tags,
        ))
    return rows
