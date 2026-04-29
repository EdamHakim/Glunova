from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class OcrEvalSample(BaseModel):
    sample_id: str
    file_path: str
    mime_type: str | None = None
    expected_document_type: str | None = None
    expected_ocr_text: str | None = None
    expected_extracted_json: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None

    def resolved_path(self, dataset_path: Path) -> Path:
        candidate = Path(self.file_path)
        if candidate.is_absolute():
            return candidate
        return (dataset_path.parent / candidate).resolve()
