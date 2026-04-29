from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class EvalSample:
    sample_id: str
    question: str
    expected_answer: str
    preferred_language: str = "en"
    patient_id: int = 999001
    expected_technique: str | None = None
    expected_recommendation: str | None = None
    tags: list[str] | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def load_eval_samples(path: Path) -> list[EvalSample]:
    samples: list[EvalSample] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            samples.append(
                EvalSample(
                    sample_id=str(payload["sample_id"]),
                    question=str(payload["question"]),
                    expected_answer=str(payload.get("expected_answer") or ""),
                    preferred_language=str(payload.get("preferred_language") or "en"),
                    patient_id=int(payload.get("patient_id") or 999001),
                    expected_technique=payload.get("expected_technique"),
                    expected_recommendation=payload.get("expected_recommendation"),
                    tags=[str(tag) for tag in (payload.get("tags") or [])],
                )
            )
    return samples


def save_eval_samples(path: Path, samples: list[EvalSample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for sample in samples:
            handle.write(json.dumps(sample.to_json(), ensure_ascii=False) + "\n")
