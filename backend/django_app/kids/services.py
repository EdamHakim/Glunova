from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from .models import KidsInstructionChunk, KidsInstructionDocument

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "is",
    "are",
    "was",
    "were",
    "be",
    "from",
    "that",
    "this",
    "it",
}


def _tokenize(text: str) -> list[str]:
    tokens = [token.lower() for token in _TOKEN_RE.findall(text or "")]
    return [token for token in tokens if token not in _STOPWORDS and len(token) > 1]


def split_text(text: str, chunk_size: int = 450, overlap: int = 80) -> list[str]:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunks.append(cleaned[start:end])
        if end == len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def extract_instruction_lines(text: str) -> list[str]:
    lines = [line.strip(" -*\t•■—–") for line in (text or "").splitlines() if line.strip()]
    structured = extract_instruction_checklist(text)
    if structured:
        extracted: list[str] = []
        for section, items in structured.items():
            extracted.extend(f"{section.upper()}: {item}" for item in items)
        return extracted[:30]
    heuristics = ("do not", "don't", "must", "avoid", "should", "allowed", "forbidden", "no ")
    extracted = [line for line in lines if any(token in line.lower() for token in heuristics)]
    if extracted:
        return extracted[:30]
    # Fallback: split by sentence if no explicit rule-like line is found.
    sentences = [s.strip() for s in re.split(r"[.!?]+", text or "") if s.strip()]
    return sentences[:20]


def extract_instruction_checklist(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"avoid": [], "do": [], "alert": []}
    current: str | None = None
    ignored_fragments = (
        "daily health",
        "important instructions",
        "follow these",
        "foods & drinks",
        "healthy habits",
        "tell a parent",
    )

    for raw_line in (text or "").splitlines():
        line = raw_line.strip(" -*\t•■—–")
        if not line:
            continue
        lowered = line.lower()
        if "avoid" in lowered:
            current = "avoid"
            continue
        if lowered.startswith("do ") or lowered == "do" or "healthy habits" in lowered:
            current = "do"
            continue
        if "alert" in lowered or "tell a parent" in lowered:
            current = "alert"
            continue
        if current is None:
            continue
        if any(fragment in lowered for fragment in ignored_fragments):
            continue
        if len(line) > 140:
            continue
        sections[current].append(line)

    if not any(sections.values()):
        lowered_text = " ".join((text or "").lower().split())
        known_avoid = [
            ("candy", "Candy"),
            ("soda", "Soda"),
            ("juice", "Juice"),
            ("desserts with added sugar", "Desserts with added sugar"),
        ]
        known_do = [
            ("drink water", "Drink water throughout the day"),
            ("balanced meals", "Eat balanced meals with protein and vegetables"),
            ("protein and vegetables", "Eat balanced meals with protein and vegetables"),
            ("check blood sugar", "Check blood sugar before breakfast and before bedtime"),
            ("before breakfast", "Check blood sugar before breakfast and before bedtime"),
            ("before bedtime", "Check blood sugar before breakfast and before bedtime"),
            ("take insulin", "Take insulin exactly as prescribed"),
            ("never skip", "Take insulin exactly as prescribed"),
            ("change the dose", "Take insulin exactly as prescribed"),
        ]
        known_alert = [
            ("shaky", "Shaky"),
            ("dizzy", "Dizzy"),
            ("very thirsty", "Very thirsty"),
            ("unusually tired", "Unusually tired"),
        ]
        sections["avoid"] = [label for needle, label in known_avoid if needle in lowered_text]
        sections["do"] = list(dict.fromkeys(label for needle, label in known_do if needle in lowered_text))
        sections["alert"] = [label for needle, label in known_alert if needle in lowered_text]

    return {section: items for section, items in sections.items() if items}


def format_instruction_checklist(checklist: dict[str, list[str]]) -> str:
    if not checklist:
        return ""
    labels = {
        "avoid": "Avoid these",
        "do": "Do these",
        "alert": "Tell a parent if you feel",
    }
    parts = []
    for section in ("avoid", "do", "alert"):
        items = checklist.get(section) or []
        if items:
            parts.append(f"{labels[section]}: {', '.join(items)}")
    return "\n".join(parts)


def rebuild_instruction_index(document: KidsInstructionDocument) -> None:
    document.chunks.all().delete()
    chunks = split_text(document.document_text)
    to_create: list[KidsInstructionChunk] = []
    for idx, chunk in enumerate(chunks):
        token_set = sorted(set(_tokenize(chunk)))
        to_create.append(
            KidsInstructionChunk(
                document=document,
                chunk_text=chunk,
                token_set=token_set,
                sequence=idx,
            )
        )
    if to_create:
        KidsInstructionChunk.objects.bulk_create(to_create)


def retrieve_relevant_chunks(patient_id: int, query: str, limit: int = 4) -> list[KidsInstructionChunk]:
    tokens = _tokenize(query)
    token_counter = Counter(tokens)
    candidates = list(
        KidsInstructionChunk.objects.filter(document__patient_id=patient_id, document__is_active=True)
        .select_related("document")
        .order_by("document_id", "sequence")
    )
    if not candidates:
        return []
    if not token_counter:
        return candidates[:limit]

    scored: list[tuple[int, KidsInstructionChunk]] = []
    for chunk in candidates:
        overlap = len(set(chunk.token_set) & set(token_counter))
        if overlap:
            scored.append((overlap, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:limit]]


def summarize_rules_for_prompt(rules: Iterable[str]) -> str:
    cleaned = [rule.strip() for rule in rules if isinstance(rule, str) and rule.strip()]
    if not cleaned:
        return "No doctor instructions found yet."
    bullets = "\n".join(f"- {rule}" for rule in cleaned[:12])
    return f"Doctor instructions:\n{bullets}"
