from __future__ import annotations

import asyncio
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from extraction.evaluation.dataset_schema import OcrEvalSample


@dataclass(slots=True)
class OcrEvalRuntimeRow:
    sample_id: str
    file_path: str
    mime_type: str
    expected_document_type: str | None
    expected_ocr_text: str | None
    expected_extracted_json: dict[str, Any]
    actual_ocr_text: str
    actual_extracted_json: dict[str, Any]
    extracted_json_rules: dict[str, Any]
    confidence_score: float | None
    review_required: bool
    status: str
    notes: str | None


def load_eval_dataset(dataset_path: Path) -> list[OcrEvalSample]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    rows: list[OcrEvalSample] = []
    for index, line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {index} in {dataset_path}: {exc}") from exc
        rows.append(OcrEvalSample.model_validate(payload))
    return rows


def _infer_mime_type(path: Path, configured: str | None) -> str:
    if configured:
        return configured
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


async def _run_extraction(file_bytes: bytes, mime_type: str, *, ocr_backend: str) -> dict[str, Any]:
    from extraction.services.orchestrator import extract_document_payload

    return await extract_document_payload(file_bytes, mime_type, ocr_backend=ocr_backend)


async def build_runtime_rows(
    dataset_path: Path,
    *,
    ocr_backend: str = "auto",
) -> list[OcrEvalRuntimeRow]:
    rows: list[OcrEvalRuntimeRow] = []
    for sample in load_eval_dataset(dataset_path):
        resolved_path = sample.resolved_path(dataset_path)
        file_bytes = resolved_path.read_bytes()
        mime_type = _infer_mime_type(resolved_path, sample.mime_type)
        payload = await _run_extraction(file_bytes, mime_type, ocr_backend=ocr_backend)
        rows.append(
            OcrEvalRuntimeRow(
                sample_id=sample.sample_id,
                file_path=str(resolved_path),
                mime_type=mime_type,
                expected_document_type=sample.expected_document_type,
                expected_ocr_text=sample.expected_ocr_text,
                expected_extracted_json=sample.expected_extracted_json,
                actual_ocr_text=payload["raw_ocr_text"],
                actual_extracted_json=payload["extracted_json"],
                extracted_json_rules=payload["extracted_json_rules"],
                confidence_score=payload["confidence_score"],
                review_required=bool(payload["review_required"]),
                status=str(payload["status"]),
                notes=sample.notes,
            )
        )
    return rows


def build_runtime_rows_sync(
    dataset_path: Path,
    *,
    ocr_backend: str = "auto",
) -> list[OcrEvalRuntimeRow]:
    return asyncio.run(build_runtime_rows(dataset_path, ocr_backend=ocr_backend))
