from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class WellnessEvalSample:
    sample_id:            str
    patient_context:      str        # JSON string of WeeklyWellnessPlanRequest fields
    day_index:            int        # 0–6: the specific day being evaluated
    expected_day_summary: str        # natural-language description of a correct day
    tags:                 list[str] = field(default_factory=list)
    # e.g. ["active_day", "heart_disease:False", "hba1c:controlled", "allergy:peanuts"]
