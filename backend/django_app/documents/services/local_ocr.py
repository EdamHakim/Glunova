"""Local OCR helpers for images and text-based PDFs."""

from __future__ import annotations

from io import BytesIO


def extract_local_ocr_text(file_bytes: bytes, mime_type: str, language: str = "eng") -> str:
    if mime_type == "application/pdf":
        text = _extract_pdf_text(file_bytes)
        if text.strip():
            return text
        return ""

    if mime_type.startswith("image/"):
        return _extract_image_text(file_bytes, language)

    return ""


def _extract_pdf_text(file_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(BytesIO(file_bytes))
    except Exception:
        return ""

    chunks: list[str] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            chunks.append(page_text)
    return "\n\n".join(chunks).strip()


def _extract_image_text(file_bytes: bytes, language: str) -> str:
    try:
        import pytesseract
        from PIL import Image, ImageOps
    except ImportError:
        return ""

    try:
        with Image.open(BytesIO(file_bytes)) as image:
            # Basic normalization helps Tesseract on phone photos and scans.
            prepared = ImageOps.exif_transpose(image).convert("L")
            return pytesseract.image_to_string(prepared, lang=language).strip()
    except Exception:
        return ""
