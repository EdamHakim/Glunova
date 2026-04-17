from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from extraction.services.local_ocr import extract_local_ocr_payload


class LocalOcrObservabilityTests(TestCase):
    @patch("extraction.services.local_ocr._extract_pdf_image_payload")
    @patch("extraction.services.local_ocr._extract_pdf_text")
    def test_digital_pdf_keeps_fast_text_path(
        self,
        mock_extract_pdf_text,
        mock_extract_pdf_image_payload,
    ) -> None:
        mock_extract_pdf_text.return_value = "digital pdf text " * 10

        payload = extract_local_ocr_payload(b"%PDF", "application/pdf", "eng")

        self.assertIn("digital pdf text", payload["text"])
        self.assertEqual(payload["meta"]["source"], "pdf_text")
        self.assertFalse(payload["meta"]["used_raster_fallback"])
        mock_extract_pdf_image_payload.assert_not_called()

    @patch("extraction.services.local_ocr._extract_pdf_image_payload")
    @patch("extraction.services.local_ocr._extract_pdf_text")
    def test_scanned_pdf_falls_back_and_surfaces_low_quality_signal(
        self,
        mock_extract_pdf_text,
        mock_extract_pdf_image_payload,
    ) -> None:
        mock_extract_pdf_text.return_value = "too short"
        mock_extract_pdf_image_payload.return_value = {
            "text": "",
            "meta": {
                "source": "pdf_raster",
                "used_raster_fallback": True,
                "average_confidence": 31.5,
                "confidence_available": True,
                "page_count": 1,
                "low_quality": True,
                "note": "OCR low confidence - please retake photo",
            },
        }

        payload = extract_local_ocr_payload(b"%PDF", "application/pdf", "eng")

        self.assertEqual(payload["text"], "")
        self.assertEqual(payload["meta"]["source"], "pdf_raster")
        self.assertTrue(payload["meta"]["used_raster_fallback"])
        self.assertTrue(payload["meta"]["low_quality"])
        self.assertEqual(payload["meta"]["note"], "OCR low confidence - please retake photo")
