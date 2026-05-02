"""Sanadi markdown KB chunking / topic tagging."""

from __future__ import annotations

from pathlib import Path

from psychology.chunking import (
    chunk_sanadi_kb_markdown,
    pack_markdown_kb_body,
    sanadi_section_topic,
)


def test_sanadi_section_topic_buckets() -> None:
    assert sanadi_section_topic(0) == "meta"
    assert sanadi_section_topic(1) == "concept"
    assert sanadi_section_topic(2) == "assessment"
    assert sanadi_section_topic(12) == "assessment"
    assert sanadi_section_topic(13) == "intervention"
    assert sanadi_section_topic(21) == "referral"
    assert sanadi_section_topic(22) == "care_system"
    assert sanadi_section_topic(26) == "lifestyle_communication"
    assert sanadi_section_topic(27) == "disordered_eating"
    assert sanadi_section_topic(28) == "assistant_routing"


def test_pack_markdown_kb_body_multi_paragraph_pack() -> None:
    """Markdown packer splits long prose without invoking PDF cleaners."""
    body = (
        "Introduction paragraph carries substantive clinical wording for retrieval quality checks. "
        "* 42\n\n"
        "Follow-on paragraph repeats wording for packing tests sufficiently. " * 18
    )
    parts = pack_markdown_kb_body(body, chunk_size=320)
    assert len(parts) >= 2
    merged = "\n".join(parts)
    assert "Introduction paragraph" in merged
    assert "Follow-on paragraph" in merged


def test_chunk_sanadi_kb_real_file_sections() -> None:
    root = Path(__file__).resolve().parents[3] / "psychology data" / "sanadi_knowledge_base.md"
    if not root.is_file():
        raise AssertionError(f"fixture missing: {root}")
    raw = root.read_text(encoding="utf-8")
    chunks = chunk_sanadi_kb_markdown(raw)
    by_id = {str(c["chunk_id"]): c for c in chunks}
    assert len(chunks) == 29
    assert by_id["SANADI_PREAMBLE"]["sanadi_topic"] == "meta"
    assert by_id["SANADI_PREAMBLE"]["section_index"] == 0
    assert by_id["SANADI_S01"]["sanadi_topic"] == "concept"
    assert by_id["SANADI_S01"]["section_index"] == 1
    assert by_id["SANADI_S02"]["sanadi_topic"] == "assessment"
    assert by_id["SANADI_S21"]["sanadi_topic"] == "referral"
    assert by_id["SANADI_S28"]["sanadi_topic"] == "assistant_routing"


def test_chunk_sanadi_minimal_fixture() -> None:
    raw = (
        "# Title line\n\nPreamble prose with enough letters for quality threshold validation here.\n\n"
        "---\n\n"
        "## SECTION 1 — Test Section\n\n"
        "First paragraph in section one with adequate length.\n\n"
        "Second paragraph continues the clinical content meaningfully.\n"
    )
    chunks = chunk_sanadi_kb_markdown(raw)
    ids = [c["chunk_id"] for c in chunks]
    assert "SANADI_PREAMBLE" in ids
    assert any(i.startswith("SANADI_S01") for i in ids)
    sec = next(c for c in chunks if c["chunk_id"].startswith("SANADI_S01"))
    assert sec["sanadi_topic"] == "concept"
    assert sec["section_index"] == 1
