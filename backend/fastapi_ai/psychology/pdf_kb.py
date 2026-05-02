"""Extract text from local psychology KB PDFs under the repo `psychology data/` tree."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)

# Max limits keep reindex bounded on huge PDFs.
_MAX_PDF_PAGES = 320
_MAX_PDF_CHARS = 900_000
SUPPORTED_EXTRACTORS = {"pypdf", "chonkie"}

# Curated RAG source: single markdown file (replaces PDF corpus when present under `psychology data/`).
SANADI_KB_MARKDOWN = "sanadi_knowledge_base.md"


def repo_root() -> Path:
    """`backend/fastapi_ai/psychology/pdf_kb.py` → Glunova repo root."""
    return Path(__file__).resolve().parents[3]


def resolve_psychology_data_dir() -> Path | None:
    raw = (getattr(settings, "psychology_data_dir", None) or "").strip()
    if raw:
        p = Path(raw).expanduser()
        return p if p.is_dir() else None
    auto = repo_root() / "psychology data"
    return auto if auto.is_dir() else None


def resolve_sanadi_kb_markdown_path() -> Path | None:
    """Path to `sanadi_knowledge_base.md` when the psychology data directory is available."""
    root = resolve_psychology_data_dir()
    if root is None:
        return None
    path = root / SANADI_KB_MARKDOWN
    return path if path.is_file() else None


def sanadi_kb_document_meta(rel_path_posix: str) -> dict[str, Any]:
    """Qdrant payload metadata for markdown KB chunks (parallel shape to `pdf_document_meta`)."""
    return {
        "source": "Sanadi Clinical Knowledge Base",
        "category": "sanadi_clinical_kb",
        "url": f"local:{rel_path_posix}",
        "language": "en",
        "file_path": rel_path_posix,
        "content_kind": "sanadi_kb_md",
    }


def stable_point_id(*parts: str) -> int:
    """Deterministic Qdrant point id in [0, 2**63 - 1]."""
    h = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big", signed=False) % (2**63)


def _category_for_relative_path(rel: str) -> str:
    lower = rel.lower()
    if "idf" in lower:
        return "diabetes_guidelines"
    if "ditress" in lower or "distress" in lower or "dds" in lower:
        return "distress_scales"
    if "ada" in lower or "mental_health" in lower or "section" in lower or "toolkit" in lower or "position" in lower:
        return "ada_guidelines"
    return "clinical_reference"


def _extract_pdf_text_pypdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pypdf is required for PDF ingestion") from exc

    reader = PdfReader(str(path))
    parts: list[str] = []
    total_chars = 0
    for i, page in enumerate(reader.pages):
        if i >= _MAX_PDF_PAGES:
            logger.warning("PDF page cap reached (%s): %s", _MAX_PDF_PAGES, path)
            break
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
            total_chars += len(text)
        if total_chars >= _MAX_PDF_CHARS:
            logger.warning("PDF character cap reached (%s): %s", _MAX_PDF_CHARS, path)
            break
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(parts)).strip()


def _extract_pdf_text_chonkie(path: Path) -> str:
    """
    Best-effort Chonkie extraction.
    Falls back to pypdf if Chonkie is unavailable or API surface differs.
    """
    try:
        import chonkie  # type: ignore # noqa: F401
        # Chonkie API is not stable across releases; for now we rely on pypdf extraction
        # and keep this branch as explicit feature toggle + hook.
        logger.info("Chonkie extractor requested; using pypdf text extraction compatibility path")
    except Exception as exc:
        logger.warning("Chonkie not available (%s). Falling back to pypdf extractor.", exc)
    return _extract_pdf_text_pypdf(path)


def extract_pdf_text(path: Path, extractor: str = "pypdf") -> str:
    mode = (extractor or "pypdf").strip().lower()
    if mode not in SUPPORTED_EXTRACTORS:
        raise RuntimeError(f"Unsupported extractor '{extractor}'. Supported: {sorted(SUPPORTED_EXTRACTORS)}")
    if mode == "chonkie":
        return _extract_pdf_text_chonkie(path)
    return _extract_pdf_text_pypdf(path)


def discover_pdf_files(root: Path) -> list[Path]:
    files = sorted(root.rglob("*.pdf"))
    return [p for p in files if p.is_file()]


def pdf_document_meta(path: Path, root: Path) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    display = path.stem.replace("_", " ").strip() or path.name
    return {
        "source": display,
        "category": _category_for_relative_path(rel),
        "url": f"local:{rel}",
        "language": "en",
        "file_path": rel,
        "content_kind": "pdf",
    }
