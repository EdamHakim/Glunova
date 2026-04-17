"""Local OCR helpers for images and PDFs."""

from __future__ import annotations

from io import BytesIO
from typing import Any


_PDF_TEXT_MIN_CHARS = 80
_LOW_OCR_TEXT_MIN_CHARS = 20
_PDF_RASTER_MAX_PAGES = 5
_PDF_RASTER_DPI = 200


def extract_local_ocr_text(file_bytes: bytes, mime_type: str, language: str = "eng") -> str:
    return extract_local_ocr_payload(file_bytes, mime_type, language)["text"]


def extract_local_ocr_payload(file_bytes: bytes, mime_type: str, language: str = "eng") -> dict[str, Any]:
    meta: dict[str, Any] = {
        "mime_type": mime_type,
        "ocr_engine": "tesseract",
        "source": "unsupported",
        "used_raster_fallback": False,
        "average_confidence": None,
        "confidence_available": False,
        "low_quality": False,
        "note": None,
    }

    if mime_type == "application/pdf":
        text = _extract_pdf_text(file_bytes)
        if len(text.strip()) >= _PDF_TEXT_MIN_CHARS:
            meta["source"] = "pdf_text"
            return {"text": text, "meta": meta}

        raster = _extract_pdf_image_payload(file_bytes, language)
        meta.update(raster["meta"])
        meta["source"] = "pdf_raster"
        meta["used_raster_fallback"] = True
        return {"text": raster["text"], "meta": meta}

    if mime_type.startswith("image/"):
        image_payload = _extract_image_payload(file_bytes, language)
        meta.update(image_payload["meta"])
        meta["source"] = "image"
        return {"text": image_payload["text"], "meta": meta}

    meta["note"] = "Unsupported MIME type for local OCR"
    return {"text": "", "meta": meta}


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


def _extract_pdf_image_text(file_bytes: bytes, language: str) -> str:
    return _extract_pdf_image_payload(file_bytes, language)["text"]


def _extract_pdf_image_payload(file_bytes: bytes, language: str) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "source": "pdf_raster",
        "used_raster_fallback": True,
        "average_confidence": None,
        "confidence_available": False,
        "page_count": 0,
        "low_quality": False,
        "note": None,
    }
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        meta["note"] = "pdf2image is not installed; raster OCR skipped"
        meta["low_quality"] = True
        return {"text": "", "meta": meta}

    try:
        max_pages = _PDF_RASTER_MAX_PAGES
        dpi = _PDF_RASTER_DPI
        poppler_path = None
        images = convert_from_bytes(
            file_bytes,
            dpi=dpi,
            first_page=1,
            last_page=max_pages,
            fmt="png",
            poppler_path=poppler_path,
        )
    except Exception:
        meta["note"] = "PDF rasterization failed; OCR unavailable for scanned PDF"
        meta["low_quality"] = True
        return {"text": "", "meta": meta}

    chunks: list[str] = []
    confidences: list[float] = []
    for index, image in enumerate(images, start=1):
        page_payload = _extract_image_payload(_image_to_png_bytes(image), language)
        page_text = page_payload["text"]
        page_meta = page_payload["meta"]
        if page_text:
            chunks.append(f"[page {index}]\n{page_text}")
        if isinstance(page_meta.get("average_confidence"), (int, float)):
            confidences.append(float(page_meta["average_confidence"]))

    text = "\n\n".join(chunks).strip()
    meta["page_count"] = len(images)
    if confidences:
        meta["average_confidence"] = round(sum(confidences) / len(confidences), 2)
        meta["confidence_available"] = True
    if len(text.strip()) < _LOW_OCR_TEXT_MIN_CHARS:
        meta["low_quality"] = True
        meta["note"] = "OCR low confidence - please retake photo"
    return {"text": text, "meta": meta}


def _image_to_png_bytes(image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _prepare_image(image):
    from PIL import ImageEnhance, ImageOps

    prepared = ImageOps.exif_transpose(image).convert("L")
    width, height = prepared.size
    max_dim = 2200
    min_dim = 1200

    longest_side = max(width, height)
    shortest_side = min(width, height)
    scale = 1.0
    if longest_side > max_dim:
        scale = min(scale, max_dim / longest_side)
    if shortest_side < min_dim:
        scale = max(scale, min_dim / max(shortest_side, 1))

    if abs(scale - 1.0) > 0.01:
        resized = (
            max(1, int(round(width * scale))),
            max(1, int(round(height * scale))),
        )
        prepared = prepared.resize(resized)

    contrast = 1.35
    if contrast != 1.0:
        prepared = ImageEnhance.Contrast(prepared).enhance(contrast)

    threshold = 170
    # Always binarize for OCR in this context
    prepared = prepared.point(lambda value: 255 if value >= threshold else 0)
    return prepared


def _tesseract_config() -> str:
    psm = 6
    oem = 3
    return f"--psm {psm} --oem {oem}"


def _extract_image_text(file_bytes: bytes, language: str) -> str:
    return _extract_image_payload(file_bytes, language)["text"]


def _extract_image_payload(file_bytes: bytes, language: str) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "source": "image",
        "average_confidence": None,
        "confidence_available": False,
        "low_quality": False,
        "note": None,
    }
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        meta["note"] = "pytesseract or Pillow is not installed"
        meta["low_quality"] = True
        return {"text": "", "meta": meta}

    try:
        with Image.open(BytesIO(file_bytes)) as image:
            prepared = _prepare_image(image)
            text = pytesseract.image_to_string(prepared, lang=language, config=_tesseract_config()).strip()
            confidence = _compute_average_confidence(prepared, language)
            if confidence is not None:
                meta["average_confidence"] = confidence
                meta["confidence_available"] = True
            if len(text.strip()) < _LOW_OCR_TEXT_MIN_CHARS:
                meta["low_quality"] = True
                meta["note"] = "OCR low confidence - please retake photo"
            return {"text": text, "meta": meta}
    except Exception:
        meta["low_quality"] = True
        meta["note"] = "Image OCR failed"
        return {"text": "", "meta": meta}


def _compute_average_confidence(image, language: str) -> float | None:
    try:
        import pytesseract
    except ImportError:
        return None

    try:
        data = pytesseract.image_to_data(
            image,
            lang=language,
            config=_tesseract_config(),
            output_type=pytesseract.Output.DICT,
        )
    except Exception:
        return None

    confidences: list[float] = []
    for raw_confidence in data.get("conf", []):
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            continue
        if confidence >= 0:
            confidences.append(confidence)

    if not confidences:
        return None

    return round(sum(confidences) / len(confidences), 2)
