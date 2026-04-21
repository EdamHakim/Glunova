from __future__ import annotations

import re
from typing import Any


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_inline_citations(text: str) -> str:
    text = re.sub(r"\(\s*\d+(?:\s*,\s*\d+)*\s*\)", "", text)
    text = re.sub(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _section(text: str, start_pat: str, end_pats: list[str]) -> str:
    m = re.search(start_pat, text, flags=re.I | re.S)
    if not m:
        return ""
    start = m.start()
    end = len(text)
    tail = text[start:]
    for pat in end_pats:
        e = re.search(pat, tail, flags=re.I | re.S)
        if e:
            end = min(end, start + e.start())
    return text[start:end].strip()


def _make(chunk_id: str, text: str, **meta: str) -> dict[str, Any]:
    return {"chunk_id": chunk_id, "text": _norm(text), "metadata": meta}


def _extract_dds17(raw: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    # Items: Q1..Q17 block
    items = re.findall(r"(Q(?:1[0-7]|[1-9])\s+.+?)(?=\s+Q(?:1[0-7]|[1-9])\s+|$)", raw, flags=re.S | re.I)
    if items:
        items_txt = "\n".join(_norm(i) for i in items[:17])
        out.append(_make("DDS_01", items_txt, instrument="DDS17", content_type="items", domain="assessment"))

    m_score = re.search(
        r"The\s*DDS17\s*yields.+?(?=Total\s*DDS\s*Score:|A\.\s*Emotional Burden)",
        raw,
        flags=re.I | re.S,
    )
    score_block = m_score.group(0).strip() if m_score else ""
    if score_block:
        out.append(
            _make(
                "DDS_02",
                score_block,
                instrument="DDS17",
                content_type="scoring_rules",
                domain="assessment",
            )
        )

    sub = _section(
        raw,
        r"A\.\s*Emotional Burden.+?",
        [r"Reference", r"DDS1\.1", r"$"],
    )
    if sub:
        out.append(
            _make(
                "DDS_03",
                sub,
                instrument="DDS17",
                content_type="subscales",
                domain="assessment",
            )
        )
    return out


def _extract_toolkit(raw: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    paid_items = _section(raw, r"Problem Areas In Diabetes\s*\(PAID\).+?Instructions:.*?", [r"Scoring", r"PHQ-9", r"GAD-7"])
    if paid_items:
        out.append(_make("ADA_TK_01", paid_items, instrument="PAID", content_type="items", domain="assessment"))
    paid_scoring = _section(raw, r"Scoring.*?(PAID|score).*?", [r"PHQ-9", r"GAD-7"])
    if paid_scoring:
        out.append(_make("ADA_TK_02", paid_scoring, instrument="PAID", content_type="scoring_rules", domain="assessment"))
    phq = _section(raw, r"PHQ-9.+?", [r"GAD-7", r"Generalized Anxiety Disorder", r"$"])
    if phq:
        out.append(_make("ADA_TK_03", phq, instrument="PHQ-9", content_type="items_thresholds", domain="assessment"))
    gad = _section(raw, r"GAD-7.+?", [r"Appendix", r"References", r"$"])
    if gad:
        out.append(_make("ADA_TK_04", gad, instrument="GAD-7", content_type="items_thresholds", domain="assessment"))
    preamble = _section(raw, r"Diabetes and Emotional Health guide.+?", [r"Problem Areas In Diabetes", r"PHQ-9", r"GAD-7"])
    if preamble:
        out.append(_make("ADA_TK_05", preamble, instrument="ADA_TOOLKIT", content_type="clinical_guidance", domain="assessment"))
    return out


def _extract_ada_section5(raw: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    # Keep psychosocial parts only.
    lower_raw = raw.lower()
    start = lower_raw.find("psychosocial care")
    if start < 0:
        return out
    end_sleep = lower_raw.find("sleep health", start + 10)
    end_tobacco = lower_raw.find("tobacco cessation", start + 10)
    end = len(raw)
    if end_sleep > start:
        end = min(end, end_sleep)
    if end_tobacco > start:
        end = min(end, end_tobacco)
    psycho = raw[start:end].strip()
    psycho = _strip_inline_citations(psycho)

    low = psycho.lower()
    anchors = [
        ("psychosocial care", "ADA_S5_01", "psychosocial_overview"),
        ("diabetes distress", "ADA_S5_02", "diabetes_distress"),
        ("depression", "ADA_S5_03", "depression"),
        ("anxiety", "ADA_S5_04", "anxiety_fear_hypo"),
        ("disordered eating", "ADA_S5_05", "disordered_eating"),
    ]
    positions: list[tuple[int, str, str]] = []
    for label, cid, ctype in anchors:
        idx = low.find(label)
        if idx >= 0:
            positions.append((idx, cid, ctype))
    positions.sort(key=lambda x: x[0])
    for i, (start, cid, ctype) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(psycho)
        sec = psycho[start:end].strip()
        if sec:
            out.append(_make(cid, _strip_inline_citations(sec), instrument="ADA_S5_2026", content_type=ctype, domain="psychosocial"))

    referral = _section(
        psycho,
        r"(Referral|refer).+?mental health.+?",
        [r"SLEEP HEALTH", r"TOBACCO CESSATION", r"$"],
    )
    if referral:
        out.append(_make("ADA_S5_06", _strip_inline_citations(referral), instrument="ADA_S5_2026", content_type="escalation_referral", domain="psychosocial"))
    return out


def curated_chunks_for_pdf(filename: str, raw_text: str) -> list[dict[str, Any]]:
    name = filename.lower()
    if "diabetes-ditress-screening-scale" in name or "dds" in name:
        return _extract_dds17(raw_text)
    if "ada_mental_health_toolkit_questionnaires" in name:
        return _extract_toolkit(raw_text)
    if "full section 5" in name:
        return _extract_ada_section5(raw_text)
    if "idf_rec_2025" in name:
        # Explicitly excluded by product requirement (psychosocial signal/noise tradeoff).
        return []
    return []

