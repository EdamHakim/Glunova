from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from extraction.evaluation.run_deepeval_eval import run_deepeval_eval
from extraction.evaluation.runner import OcrEvalRuntimeRow, build_runtime_rows_sync, load_eval_dataset


class ExtractionEvaluationRunnerTests(TestCase):
    def _make_tmp_dir(self) -> Path:
        root = Path("tmp/test_extraction_eval")
        root.mkdir(parents=True, exist_ok=True)
        path = root / uuid4().hex
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_load_eval_dataset_reads_jsonl(self) -> None:
        tmp_path = self._make_tmp_dir()
        dataset_path = tmp_path / "dataset.jsonl"
        dataset_path.write_text(
            json.dumps(
                {
                    "sample_id": "sample-1",
                    "file_path": "doc.pdf",
                    "expected_document_type": "lab_report",
                    "expected_extracted_json": {"document_type": "lab_report"},
                }
            ),
            encoding="utf-8",
        )

        rows = load_eval_dataset(dataset_path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].sample_id, "sample-1")
        self.assertEqual(rows[0].file_path, "doc.pdf")

    @patch("extraction.evaluation.runner._run_extraction")
    def test_build_runtime_rows_uses_shared_orchestrator(self, mock_run_extraction) -> None:
        mock_run_extraction.return_value = {
            "raw_ocr_text": "GLYCEMIE 1.06 g/L",
            "extracted_json": {"document_type": "lab_report"},
            "extracted_json_rules": {"document_type": "lab_report"},
            "field_evidence": {},
            "status": "ok",
            "review_required": False,
            "confidence_score": 91.5,
        }

        tmp_path = self._make_tmp_dir()
        document_path = tmp_path / "doc.pdf"
        document_path.write_bytes(b"%PDF-1.4")
        dataset_path = tmp_path / "dataset.jsonl"
        dataset_path.write_text(
            json.dumps(
                {
                    "sample_id": "sample-1",
                    "file_path": "doc.pdf",
                    "mime_type": "application/pdf",
                    "expected_document_type": "lab_report",
                    "expected_extracted_json": {"document_type": "lab_report"},
                }
            ),
            encoding="utf-8",
        )

        rows = build_runtime_rows_sync(dataset_path, ocr_backend="local")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].actual_ocr_text, "GLYCEMIE 1.06 g/L")
        self.assertEqual(rows[0].confidence_score, 91.5)

    def test_run_deepeval_eval_falls_back_without_package(self) -> None:
        rows = [
            OcrEvalRuntimeRow(
                sample_id="sample-1",
                file_path="doc.pdf",
                mime_type="application/pdf",
                expected_document_type="lab_report",
                expected_ocr_text="GLYCEMIE 1.06 g/L",
                expected_extracted_json={"document_type": "lab_report"},
                actual_ocr_text="GLYCEMIE 1.06 g/L",
                actual_extracted_json={"document_type": "lab_report"},
                extracted_json_rules={"document_type": "lab_report"},
                confidence_score=90.0,
                review_required=False,
                status="ok",
                notes=None,
            )
        ]

        report = run_deepeval_eval(rows)

        self.assertIn(report["engine"], {"fallback", "deepeval"})
        self.assertEqual(len(report["cases"]), 1)
