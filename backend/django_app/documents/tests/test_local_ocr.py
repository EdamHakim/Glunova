from __future__ import annotations

import sys
from io import BytesIO
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from documents.services.local_ocr import _extract_image_text, _extract_pdf_image_text, extract_local_ocr_text


def _png_bytes(width: int = 200, height: int = 120) -> bytes:
    from PIL import Image

    image = Image.new("RGB", (width, height), color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class LocalOcrTests(SimpleTestCase):
    @patch("documents.services.local_ocr._extract_pdf_image_text")
    @patch("documents.services.local_ocr._extract_pdf_text")
    def test_pdf_uses_fast_text_path_when_enough_text(
        self,
        mock_extract_pdf_text: Mock,
        mock_extract_pdf_image_text: Mock,
    ):
        mock_extract_pdf_text.return_value = "digital pdf text " * 10

        result = extract_local_ocr_text(b"%PDF", "application/pdf", "eng")

        self.assertIn("digital pdf text", result)
        mock_extract_pdf_image_text.assert_not_called()

    @patch("documents.services.local_ocr._extract_pdf_image_text")
    @patch("documents.services.local_ocr._extract_pdf_text")
    def test_pdf_falls_back_to_raster_ocr_when_text_too_short(
        self,
        mock_extract_pdf_text: Mock,
        mock_extract_pdf_image_text: Mock,
    ):
        mock_extract_pdf_text.return_value = "too short"
        mock_extract_pdf_image_text.return_value = "[page 1]\nscanned text"

        result = extract_local_ocr_text(b"%PDF", "application/pdf", "eng")

        self.assertEqual(result, "[page 1]\nscanned text")
        mock_extract_pdf_image_text.assert_called_once_with(b"%PDF", "eng")

    @override_settings(OCR_PDF_MAX_PAGES=3, OCR_PDF_RASTER_DPI=225, POPPLER_PATH="C:/poppler/bin")
    @patch("documents.services.local_ocr._extract_image_text")
    def test_pdf_image_fallback_respects_page_cap_and_poppler_path(self, mock_extract_image_text: Mock):
        from PIL import Image

        fake_pdf2image = Mock()
        fake_pdf2image.convert_from_bytes.return_value = [
            Image.new("RGB", (100, 100), color="white"),
            Image.new("RGB", (100, 100), color="white"),
        ]
        mock_extract_image_text.side_effect = ["page one text", "page two text"]

        with patch.dict(sys.modules, {"pdf2image": fake_pdf2image}):
            result = _extract_pdf_image_text(b"%PDF", "eng")

        self.assertIn("[page 1]\npage one text", result)
        self.assertIn("[page 2]\npage two text", result)
        fake_pdf2image.convert_from_bytes.assert_called_once_with(
            b"%PDF",
            dpi=225,
            first_page=1,
            last_page=3,
            fmt="png",
            poppler_path="C:/poppler/bin",
        )

    @override_settings(TESSERACT_PSM=4, TESSERACT_OEM=1, OCR_IMAGE_BINARIZE=False)
    @patch("pytesseract.image_to_string")
    def test_image_ocr_passes_configured_tesseract_options(self, mock_image_to_string: Mock):
        mock_image_to_string.return_value = "ocr text"

        result = _extract_image_text(_png_bytes(), "eng+fra")

        self.assertEqual(result, "ocr text")
        _image, = mock_image_to_string.call_args[0]
        self.assertEqual(_image.mode, "L")
        self.assertEqual(
            mock_image_to_string.call_args.kwargs,
            {"lang": "eng+fra", "config": "--psm 4 --oem 1"},
        )
