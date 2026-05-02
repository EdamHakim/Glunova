"""
High-signal chunking for clinical PDFs: strip boilerplate, reflow PDF line breaks,
then pack by paragraphs and sentences (not blind fixed-width windows).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

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
_AFFILIATION_CUE = re.compile(
    r"\b(university|department|faculty|school of|hospital|institute|center|centre|email|e-mail)\b",
    re.I,
)
_FRONT_MATTER_SECTION = re.compile(
    r"^\s*(abstract|author information|authors'? contributions?|funding|acknowledg(e)?ments?|"
    r"conflict of interest|disclosures?|keywords?|key words?)\b",
    re.I,
)
_AFFILIATION_PREFIX = re.compile(r"^\s*(\d+[\)\].-]\s*|[a-z]\)\s*)")


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


def _is_author_affiliation_paragraph(para: str) -> bool:
    text = para.strip()
    if not text:
        return True
    low = text.lower()
    if "correspondence to" in low:
        return True
    # Typical affiliation bullets like "1) Department of X ..."
    if _AFFILIATION_PREFIX.match(text) and _AFFILIATION_CUE.search(text):
        return True
    # Dense author listing with superscripts / separators and little semantic body.
    commas = text.count(",")
    semicolons = text.count(";")
    if (commas + semicolons) >= 6 and len(text.split()) < 90:
        if any(ch in text for ch in ("@", "†", "*", "‡")) or _AFFILIATION_CUE.search(text):
            return True
    return False


def _is_low_value_paragraph(para: str) -> bool:
    text = para.strip()
    if not text:
        return True
    if _FRONT_MATTER_SECTION.match(text):
        return True
    if _is_author_affiliation_paragraph(text):
        return True
    # Very short metadata labels.
    if len(text) < 70 and re.search(r"\b(received|accepted|published online|copyright)\b", text, re.I):
        return True
    return False


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
    paragraphs = [p for p in paragraphs if not _is_low_value_paragraph(p)]
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


# Markers after the last clinical section in `sanadi_knowledge_base.md` (metadata / EOF instructions).
_SANADI_KB_TRAILER_PREFIXES: tuple[str, ...] = (
    "## END OF DOCUMENT",
    "## Total sections:",
    "## Optimized for:",
    "## Recommended chunk size:",
    "## Recommended overlap:",
)


def _strip_sanadi_kb_trailer(text: str) -> str:
    cut = len(text)
    for prefix in _SANADI_KB_TRAILER_PREFIXES:
        idx = text.find(prefix)
        if idx >= 0:
            cut = min(cut, idx)
    return text[:cut].rstrip()


def sanadi_section_topic(section_index: int) -> str:
    """
    Coarse clinical bucket for filtering / analytics (indexed in Qdrant when present).

    Mirrors the structure of `sanadi_knowledge_base.md`: concept → instruments → interventions → systems → adjuncts.
    """
    if section_index <= 0:
        return "meta"
    if section_index == 1:
        return "concept"
    if 2 <= section_index <= 12:
        return "assessment"
    if 13 <= section_index <= 20:
        return "intervention"
    if section_index == 21:
        return "referral"
    if 22 <= section_index <= 23:
        return "care_system"
    if 24 <= section_index <= 26:
        return "lifestyle_communication"
    if section_index == 27:
        return "disordered_eating"
    if section_index >= 28:
        return "assistant_routing"
    return "general"


def _normalize_markdown_kb_body(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


_RULE_ONLY_MD_LINE = re.compile(r"^\s*-{3,}\s*$")


def pack_markdown_kb_body(body: str, chunk_size: int = _DEFAULT_CHUNK) -> list[str]:
    """
    Markdown-native packing for Sanadi oversized sections (no PDF boilerplate stripping).

    Paragraph boundaries → sentence packing → hard-split; keeps list-heavy clinical text usable.
    """
    cleaned = _normalize_markdown_kb_body(body)
    if not cleaned:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", cleaned) if p.strip()]
    paragraphs = [p for p in paragraphs if not _RULE_ONLY_MD_LINE.match(p)]

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


def chunk_sanadi_kb_markdown(
    raw: str,
    *,
    max_piece_chars: int = 3400,
    markdown_pack_size: int = _DEFAULT_CHUNK,
) -> list[dict[str, Any]]:
    """
    Split `sanadi_knowledge_base.md` into RAG chunks: primarily one vector per `## SECTION N — …`
    (author-recommended), with `pack_markdown_kb_body` if a section exceeds `max_piece_chars`.
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = _strip_sanadi_kb_trailer(text)

    first_section = re.search(r"^##\s+SECTION\s+\d+", text, flags=re.M)
    preamble = text[: first_section.start()].strip() if first_section else text.strip()

    out: list[dict[str, Any]] = []
    if preamble and len(preamble) > 40:
        body = re.sub(r"\n{3,}", "\n\n", preamble)
        out.append(
            {
                "chunk_id": "SANADI_PREAMBLE",
                "text": body,
                "section_title": "Preamble",
                "section_index": 0,
                "sanadi_topic": sanadi_section_topic(0),
            }
        )

    if not first_section:
        return [c for c in out if c.get("text", "").strip()]

    rest = text[first_section.start() :]
    section_iter = list(
        re.finditer(
            r"^##\s+(SECTION\s+(\d+)\s+—\s+.+?)\s*\n",
            rest,
            flags=re.M,
        )
    )
    for i, m in enumerate(section_iter):
        title_line = m.group(1).strip()
        sec_num = int(m.group(2))
        start = m.end()
        end = section_iter[i + 1].start() if i + 1 < len(section_iter) else len(rest)
        body = rest[start:end].strip()
        body = re.sub(r"^---\s*\n?", "", body)
        body = re.sub(r"\n---\s*$", "", body).strip()
        header = f"## {title_line}"
        full = f"{header}\n\n{body}" if body else header

        topic = sanadi_section_topic(sec_num)

        def emit_piece(piece: str, suffix: str) -> None:
            piece = piece.strip()
            if not piece or not _chunk_quality_ok(piece):
                return
            cid = f"SANADI_S{sec_num:02d}{suffix}"
            out.append(
                {
                    "chunk_id": cid,
                    "text": piece,
                    "section_title": title_line,
                    "section_index": sec_num,
                    "sanadi_topic": topic,
                }
            )

        if len(full) <= max_piece_chars:
            emit_piece(full, "")
            continue
        # Oversized section: markdown-native pack on body only; repeat header per piece.
        pack_target = body if body else full
        subchunks = pack_markdown_kb_body(pack_target, chunk_size=max(400, min(markdown_pack_size, 1400)))
        if not subchunks:
            piece = (full[:max_piece_chars] + "…").strip() if len(full) > max_piece_chars else full
            emit_piece(piece, "_part")
            continue
        for j, sub in enumerate(subchunks, start=1):
            piece = f"{header}\n\n{sub}".strip()
            emit_piece(piece, f"_{j:02d}")

    return [c for c in out if c.get("text", "").strip()]
