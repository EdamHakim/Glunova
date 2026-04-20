from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class KnowledgeSource:
    name: str
    category: str
    url: str
    notes: str
    language: str = "en"


SOURCES: list[KnowledgeSource] = [
    KnowledgeSource(
        name="Beck Institute CBT Resources",
        category="cbt_scripts",
        url="https://www.beckinstitute.org/",
        notes="Thought records, cognitive restructuring, behavioral activation.",
    ),
    KnowledgeSource(
        name="NHS IAPT CBT Manuals",
        category="cbt_scripts",
        url="https://www.england.nhs.uk/mental-health/adults/iapt/",
        notes="Structured step-by-step low-intensity CBT protocols.",
    ),
    KnowledgeSource(
        name="ADA Standards of Care Section 5",
        category="ada_guidelines",
        url="https://diabetesjournals.org/care",
        notes="Psychosocial assessment and diabetes distress guidance.",
    ),
    KnowledgeSource(
        name="UCSF DDS17",
        category="distress_scales",
        url="https://diabetesscale.org/",
        notes="Validated diabetes distress instrument.",
    ),
    KnowledgeSource(
        name="PAID Scale",
        category="distress_scales",
        url="https://www.joslin.org/",
        notes="Problem Areas in Diabetes assessment references.",
    ),
    KnowledgeSource(
        name="AFFORTHECC TCC",
        category="french_clinical",
        url="https://www.afforthecc.org/",
        notes="Native French CBT clinical handouts.",
        language="fr",
    ),
    KnowledgeSource(
        name="Federation Francaise des Diabetiques",
        category="french_clinical",
        url="https://www.federationdesdiabetiques.org/",
        notes="French diabetes psychoeducation and emotional support content.",
        language="fr",
    ),
    KnowledgeSource(
        name="HAS Psychosocial Guidance",
        category="french_clinical",
        url="https://www.has-sante.fr/",
        notes="French psychosocial care recommendations.",
        language="fr",
    ),
]


def chunk_text(content: str, chunk_size: int = 700, overlap: int = 90) -> list[str]:
    chunks: list[str] = []
    idx = 0
    while idx < len(content):
        chunk = content[idx : idx + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        idx += max(1, chunk_size - overlap)
    return chunks


def build_ingestion_manifest(sources: Iterable[KnowledgeSource] = SOURCES) -> list[dict[str, str]]:
    manifest: list[dict[str, str]] = []
    for source in sources:
        manifest.append(
            {
                "name": source.name,
                "category": source.category,
                "url": source.url,
                "language": source.language,
                "notes": source.notes,
            }
        )
    return manifest
