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

    # Robust range-based slicing: prefer explicit headings, fall back to recommendation markers.
    def pos(token: str) -> int:
        return low.find(token.lower())

    p_psy = pos("psychosocial care")
    p_dd = pos("diabetes distress recommendation")
    if p_dd < 0:
        p_dd = pos("diabetes distress recommendations")
    if p_dd < 0:
        p_dd = pos("diabetes distress")
    p_anx = pos("anxiety recommendations")
    if p_anx < 0:
        p_anx = pos("anxiety recommendation")
    if p_anx < 0:
        p_anx = pos("anxiety")
    p_dep = pos("depression recommendations")
    if p_dep < 0:
        p_dep = pos("depression")
    p_dis = pos("disordered eating behavior")
    if p_dis < 0:
        p_dis = pos("disordered eating")
    p_cog = pos("cognitive capacity and impairment")

    # Optional recommendation markers to tighten boundaries when headings are noisy.
    p_545 = pos("5.45")
    p_546 = pos("5.46")
    p_548 = pos("5.48")
    p_550 = pos("5.50")

    def sl(a: int, b: int) -> str:
        if a < 0:
            return ""
        end_pos = b if b > a else len(psycho)
        return psycho[a:end_pos].strip()

    # Overview up to first psychosocial subdomain.
    s1_end = min([x for x in (p_dd, p_545, p_anx, p_dep, p_dis) if x >= 0], default=len(psycho))
    s1 = sl(p_psy, s1_end)
    if s1:
        out.append(_make("ADA_S5_01", s1, instrument="ADA_S5_2026", content_type="psychosocial_overview", domain="psychosocial"))

    # Diabetes distress block.
    s2_end = min([x for x in (p_anx, p_546, p_dep, p_548, p_dis, p_550) if x >= 0 and x > p_dd], default=len(psycho))
    s2 = sl(p_dd, s2_end)
    if s2:
        out.append(_make("ADA_S5_02", s2, instrument="ADA_S5_2026", content_type="diabetes_distress", domain="psychosocial"))

    # Anxiety + fear hypoglycemia block.
    s4_end = min([x for x in (p_dep, p_548, p_dis, p_550) if x >= 0 and x > p_anx], default=len(psycho))
    s4 = sl(p_anx, s4_end)
    if s4:
        out.append(_make("ADA_S5_04", s4, instrument="ADA_S5_2026", content_type="anxiety_fear_hypo", domain="psychosocial"))

    # Depression block.
    s3_end = min([x for x in (p_dis, p_550, p_cog) if x >= 0 and x > p_dep], default=len(psycho))
    s3 = sl(p_dep, s3_end)
    if s3:
        out.append(_make("ADA_S5_03", s3, instrument="ADA_S5_2026", content_type="depression", domain="psychosocial"))

    # Disordered eating block.
    s5_end = min([x for x in (p_cog,) if x >= 0 and x > p_dis], default=len(psycho))
    s5 = sl(p_dis, s5_end)
    if s5:
        out.append(_make("ADA_S5_05", s5, instrument="ADA_S5_2026", content_type="disordered_eating", domain="psychosocial"))

    # Consolidated escalation/referral lines across psychosocial section.
    referral_lines: list[str] = []
    for seg in re.split(r"(?<=[.!?])\s+", psycho):
        s = seg.strip()
        if not s:
            continue
        low_s = s.lower()
        if "refer" in low_s or "referral" in low_s or "behavioral health" in low_s or "mental health professional" in low_s:
            referral_lines.append(s)
    if referral_lines:
        out.append(
            _make(
                "ADA_S5_06",
                " ".join(referral_lines[:30]),
                instrument="ADA_S5_2026",
                content_type="escalation_referral",
                domain="psychosocial",
            )
        )
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

