"""
High-signal chunking for clinical PDFs: strip boilerplate, reflow PDF line breaks,
then pack by paragraphs and sentences (not blind fixed-width windows).
"""

from __future__ import annotations

import re
from collections import Counter

_DEFAULT_CHUNK = 880
_MIN_CHUNK_CHARS = 120
_MIN_LETTER_RATIO = 0.28

_NOISE_LINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*\d{1,4}\s*$"),
    re.compile(r"^\s*\d{1,3}\s*/\s*\d{1,3}\s*$"),
    re.compile(r"^\s*(page|p\.)\s*\d{1,4}\s*$", re.I),
    re.compile(r"^\s*(fig\.?|figure|table)\s*\d+[.\s].*$", re.I),
    re.compile(r"^\s*doi:\s*10\.\S+\s*$", re.I),
    re.compile(r"^\s*https?://\S+\s*$", re.I),
    re.compile(r"^\s*www\.\S+\s*$", re.I),
    re.compile(r"^\s*Downloaded from\s+http", re.I),
    re.compile(r"^\s*This article is cited by\s+", re.I),
    re.compile(r"^\s*Author Manuscript\b", re.I),
    re.compile(r"^\s*NIH-PA Author Manuscript\b", re.I),
    re.compile(r"^\s*PMC\s+Author\s+Manuscript\b", re.I),
    re.compile(r"^\s*Accepted\s+Manuscript\b", re.I),
    re.compile(r"^\s*Running head:\s*", re.I),
    re.compile(r"^\s*Correspondence to\s+", re.I),
    re.compile(r"^\s*Copyright\s+©", re.I),
    re.compile(r"^\s*All rights reserved", re.I),
    re.compile(r"^\s*Vol\.?\s+\d+", re.I),
    re.compile(r"^\s*No\.?\s+\d+\s*$", re.I),
    re.compile(r"^\s*ISSN\b", re.I),
    re.compile(r"^\s*S\d{3,}\s*$", re.I),
    re.compile(r"^\s*Downloaded for .* at .* from .* by .* on .*", re.I),
)

_RULE_LINE = re.compile(r"^[-_=_.]{6,}\s*$")


def _is_noise_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if _RULE_LINE.match(s):
        return True
    if len(s) <= 2 and not any(c.isalpha() for c in s):
        return True
    non_alnum = sum(1 for c in s if not c.isalnum() and not c.isspace())
    if len(s) > 40 and non_alnum / max(len(s), 1) > 0.72:
        return True
    for pat in _NOISE_LINE_PATTERNS:
        if pat.search(s):
            return True
    return False


def _reflow_soft_line_breaks(text: str) -> str:
    """Join PDF hard-wraps when a line continues mid-sentence."""
    lines = text.split("\n")
    if not lines:
        return text
    ends_sentence = re.compile(r"[.!?…]\s*$")
    out: list[str] = []
    buf = lines[0].strip()
    for line in lines[1:]:
        cur = line.strip()
        if not cur:
            if buf:
                out.append(buf)
                buf = ""
            continue
        if buf and not ends_sentence.search(buf) and cur[0].islower():
            buf = f"{buf} {cur}"
        else:
            if buf:
                out.append(buf)
            buf = cur
    if buf:
        out.append(buf)
    return "\n".join(out)


def clean_pdf_kb_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    lines = text.split("\n")
    cleaned: list[str] = []
    prev_kept: str | None = None
    for raw in lines:
        s = raw.strip()
        if _is_noise_line(s):
            continue
        if prev_kept is not None and s == prev_kept:
            continue
        cleaned.append(s)
        prev_kept = s
    body = "\n".join(cleaned)
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = _reflow_soft_line_breaks(body)
    body = re.sub(r" {2,}", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = re.sub(r"\s*\|\s*DOI:\s*10\.\d{4,}/\S+", "", body, flags=re.I)
    body = re.sub(r"\bDOI:\s*10\.\d{4,}/\S+", "", body, flags=re.I)
    return body.strip()


def _chunk_quality_ok(text: str) -> bool:
    t = text.strip()
    if len(t) < _MIN_CHUNK_CHARS:
        return False
    letters = sum(1 for c in t if c.isalpha())
    if letters / max(len(t), 1) < _MIN_LETTER_RATIO:
        return False
    words = re.findall(r"[A-Za-z]{3,}", t.lower())
    if not words:
        return False
    top, cnt = Counter(words).most_common(1)[0]
    if len(words) >= 30 and cnt >= 18 and cnt / len(words) > 0.42 and len(set(words)) < 20:
        return False
    return True


def _split_sentences(block: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?…])\s+", block.strip())
    return [p.strip() for p in pieces if p.strip()]


def _emit_sentence_chunks(sentences: list[str], chunk_size: int) -> list[str]:
    out: list[str] = []
    buf = ""
    for sent in sentences:
        if len(sent) > chunk_size:
            if buf.strip():
                out.append(buf.strip())
                buf = ""
            for i in range(0, len(sent), chunk_size):
                piece = sent[i : i + chunk_size].strip()
                if piece:
                    out.append(piece)
            continue
        if len(buf) + len(sent) + 1 <= chunk_size:
            buf = f"{buf} {sent}".strip() if buf else sent
        else:
            if buf.strip():
                out.append(buf.strip())
            buf = sent
    if buf.strip():
        out.append(buf.strip())
    return out


def chunk_pdf_for_kb(text: str, chunk_size: int = _DEFAULT_CHUNK) -> list[str]:
    """
    Clean extract → paragraph boundaries → sentence packing → hard-split only when needed.
    """
    cleaned = clean_pdf_kb_text(text)
    if not cleaned:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", cleaned) if p.strip()]
    chunks: list[str] = []
    buf = ""

    def flush_buf() -> None:
        nonlocal buf
        if buf.strip():
            chunks.append(buf.strip())
        buf = ""

    for para in paragraphs:
        if len(para) <= chunk_size:
            if len(buf) + len(para) + 2 <= chunk_size:
                buf = f"{buf}\n\n{para}" if buf else para
            else:
                flush_buf()
                buf = para
            continue
        flush_buf()
        sents = _split_sentences(para)
        if len(sents) <= 1:
            chunks.extend(_emit_sentence_chunks([para], chunk_size))
        else:
            chunks.extend(_emit_sentence_chunks(sents, chunk_size))
    flush_buf()
    return [c for c in chunks if _chunk_quality_ok(c)]


def chunk_manifest_stub(text: str, chunk_size: int = 480, overlap: int = 80) -> list[str]:
    """Short synthetic manifest lines: small sliding windows."""
    chunks: list[str] = []
    idx = 0
    while idx < len(text):
        piece = text[idx : idx + chunk_size].strip()
        if piece:
            chunks.append(piece)
        idx += max(1, chunk_size - overlap)
    return chunks
