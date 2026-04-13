"""Tesseract OCR for images and PDF pages."""

from __future__ import annotations

import io
import logging
from PIL import Image, ImageOps
import pytesseract

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_MIME = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
    }
)


def configure_tesseract() -> None:
    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


def ocr_image_bytes(data: bytes) -> str:
    configure_tesseract()
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    gray = ImageOps.autocontrast(ImageOps.grayscale(img))
    return pytesseract.image_to_string(gray, lang="eng") or ""


def ocr_pdf_bytes(data: bytes) -> str:
    from pdf2image import convert_from_bytes

    configure_tesseract()
    try:
        images = convert_from_bytes(data, dpi=200, fmt="png")
    except Exception as e:
        logger.exception("pdf2image failed: %s", e)
        raise
    parts: list[str] = []
    for pil_img in images:
        gray = ImageOps.autocontrast(ImageOps.grayscale(pil_img))
        parts.append(pytesseract.image_to_string(gray, lang="eng") or "")
    return "\n\n".join(parts)


def run_ocr(file_bytes: bytes, mime_type: str) -> str:
    if mime_type == "application/pdf":
        return ocr_pdf_bytes(file_bytes)
    return ocr_image_bytes(file_bytes)
