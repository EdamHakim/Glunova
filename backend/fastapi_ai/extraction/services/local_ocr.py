"""Local OCR helpers for images and PDFs."""

from __future__ import annotations

from io import BytesIO
from core.config import settings

def extract_local_ocr_text(file_bytes: bytes, mime_type: str, language: str = "eng") -> str:
    if mime_type == "application/pdf":
        text = _extract_pdf_text(file_bytes)
        # Using a fallback threshold for OCR on PDFs if text extraction is too short
        min_chars = 80 
        if len(text.strip()) >= min_chars:
            return text
        return _extract_pdf_image_text(file_bytes, language)

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


def _extract_pdf_image_text(file_bytes: bytes, language: str) -> str:
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        return ""

    try:
        # Configuration matches settings defaults
        max_pages = 5
        dpi = 200
        poppler_path = None # Assumed to be in system PATH for the Docker container
        images = convert_from_bytes(
            file_bytes,
            dpi=dpi,
            first_page=1,
            last_page=max_pages,
            fmt="png",
            poppler_path=poppler_path,
        )
    except Exception:
        return ""

    chunks: list[str] = []
    for index, image in enumerate(images, start=1):
        page_text = _extract_image_text(_image_to_png_bytes(image), language)
        if page_text:
            chunks.append(f"[page {index}]\n{page_text}")
    return "\n\n".join(chunks).strip()


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
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    try:
        with Image.open(BytesIO(file_bytes)) as image:
            prepared = _prepare_image(image)
            return pytesseract.image_to_string(prepared, lang=language, config=_tesseract_config()).strip()
    except Exception:
        return ""
