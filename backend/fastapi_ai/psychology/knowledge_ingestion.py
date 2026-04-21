from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from core.config import settings
from psychology.chunking import chunk_manifest_stub, chunk_pdf_for_kb
from psychology.curated_kb import curated_chunks_for_pdf
from psychology.pdf_kb import (
    discover_pdf_files,
    extract_pdf_text,
    pdf_document_meta,
    resolve_psychology_data_dir,
    stable_point_id,
)

logger = logging.getLogger(__name__)


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
    root = resolve_psychology_data_dir()
    if root is not None:
        for path in discover_pdf_files(root):
            rel = path.relative_to(root).as_posix()
            meta = pdf_document_meta(path, root)
            manifest.append(
                {
                    "name": meta["source"],
                    "category": meta["category"],
                    "url": meta["url"],
                    "language": meta["language"],
                    "notes": f"Local PDF embedded to Qdrant on reindex. Path: {rel}",
                }
            )
    return manifest


class QdrantKnowledgeBase:
    def __init__(self) -> None:
        self.enabled = bool(settings.qdrant_url and settings.qdrant_api_key)
        self.collection = settings.qdrant_collection_cbt
        self.vector_size = settings.qdrant_vector_size
        self.embedding_model_name = settings.qdrant_embedding_model
        self._client = None
        self._embedder = None
        self._real_embeddings_enabled = True
        if self.enabled:
            try:
                from qdrant_client import QdrantClient  # type: ignore

                self._client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
            except Exception:
                self.enabled = False
        self._init_embedder()

    def _init_embedder(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._embedder = SentenceTransformer(self.embedding_model_name)
            dim = getattr(self._embedder, "get_sentence_embedding_dimension", lambda: None)()
            if isinstance(dim, int) and dim > 0:
                self.vector_size = dim
        except Exception:
            self._embedder = None
            self._real_embeddings_enabled = False

    def ensure_collection(self) -> bool:
        if not self.enabled or self._client is None:
            return False
        try:
            from qdrant_client.models import Distance, VectorParams  # type: ignore

            exists = self._client.collection_exists(collection_name=self.collection)
            if not exists:
                self._client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
                )
            return True
        except Exception:
            return False

    def reindex_sources(self) -> dict[str, Any]:
        """Upsert curated manifest stubs plus all PDFs under `psychology data/` (see `pdf_kb.py`)."""
        empty: dict[str, Any] = {
            "indexed_chunks": 0,
            "manifest_chunks": 0,
            "pdf_chunks": 0,
            "pdf_files_seen": 0,
            "pdf_files_indexed": 0,
        }
        if not self.enabled or self._client is None:
            return empty
        if not self.ensure_collection():
            return empty
        try:
            from qdrant_client.models import PointStruct  # type: ignore

            manifest_points: list[PointStruct] = []
            for source in SOURCES:
                content = f"{source.name}. {source.notes}. Source: {source.url}"
                for chunk in chunk_manifest_stub(content):
                    vector = self._embed_text(chunk)
                    manifest_points.append(
                        PointStruct(
                            id=stable_point_id("manifest_stub", source.name, chunk),
                            vector=vector,
                            payload={
                                "source": source.name,
                                "category": source.category,
                                "url": source.url,
                                "language": source.language,
                                "text": chunk,
                                "content_kind": "manifest_stub",
                            },
                        )
                    )

            pdf_points: list[PointStruct] = []
            pdf_files_indexed = 0
            data_root = resolve_psychology_data_dir()
            pdf_paths = discover_pdf_files(data_root) if data_root is not None else []
            for pdf_path in pdf_paths:
                try:
                    raw_text = extract_pdf_text(pdf_path)
                except Exception as exc:
                    logger.warning("Psychology PDF skipped (read error): %s — %s", pdf_path, exc)
                    continue
                if not raw_text.strip():
                    logger.warning("Psychology PDF skipped (no extractable text): %s", pdf_path)
                    continue
                meta = pdf_document_meta(pdf_path, data_root)
                file_chunks = 0
                curated = curated_chunks_for_pdf(pdf_path.name, raw_text)
                if curated:
                    for item in curated:
                        chunk = str(item.get("text", "")).strip()
                        if not chunk:
                            continue
                        payload = {**meta, "text": chunk, "chunk_id": str(item.get("chunk_id", ""))}
                        extra_meta = item.get("metadata")
                        if isinstance(extra_meta, dict):
                            payload.update({k: v for k, v in extra_meta.items() if isinstance(v, (str, int, float, bool))})
                        pdf_points.append(
                            PointStruct(
                                id=stable_point_id("pdf_curated", meta["file_path"], payload["chunk_id"], chunk),
                                vector=self._embed_text(chunk),
                                payload=payload,
                            )
                        )
                        file_chunks += 1
                else:
                    for chunk in chunk_pdf_for_kb(raw_text):
                        pdf_points.append(
                            PointStruct(
                                id=stable_point_id("pdf", meta["file_path"], chunk),
                                vector=self._embed_text(chunk),
                                payload={**meta, "text": chunk},
                            )
                        )
                        file_chunks += 1
                if file_chunks:
                    pdf_files_indexed += 1

            all_points = manifest_points + pdf_points
            if all_points:
                self._client.upsert(collection_name=self.collection, points=all_points)
            return {
                "indexed_chunks": len(all_points),
                "manifest_chunks": len(manifest_points),
                "pdf_chunks": len(pdf_points),
                "pdf_files_seen": len(pdf_paths),
                "pdf_files_indexed": pdf_files_indexed,
            }
        except Exception as exc:
            logger.exception("Qdrant reindex failed: %s", exc)
            return empty

    def search(self, query: str, language: str | None = None, limit: int = 3) -> list[dict[str, str]]:
        if not self.enabled or self._client is None or not query.strip():
            return []
        try:
            query_filter = None
            if language and language != "mixed":
                from qdrant_client.models import FieldCondition, Filter, MatchValue  # type: ignore

                query_filter = Filter(
                    should=[
                        FieldCondition(key="language", match=MatchValue(value=language)),
                        FieldCondition(key="language", match=MatchValue(value="en")),
                    ]
                )
            hits = self._client.search(
                collection_name=self.collection,
                query_vector=self._embed_text(query),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            results: list[dict[str, str]] = []
            for hit in hits:
                payload = hit.payload or {}
                results.append(
                    {
                        "source": str(payload.get("source", "")),
                        "category": str(payload.get("category", "")),
                        "language": str(payload.get("language", "")),
                        "text": str(payload.get("text", "")),
                    }
                )
            return results
        except Exception:
            return []

    def _embed_text(self, text: str) -> list[float]:
        if self._embedder is not None and self._real_embeddings_enabled:
            try:
                emb = self._embedder.encode([text], normalize_embeddings=True)
                if hasattr(emb, "tolist"):
                    return emb[0].tolist()
                return list(emb[0])
            except Exception:
                self._real_embeddings_enabled = False
        return self._fallback_embed_text(text)

    def _fallback_embed_text(self, text: str) -> list[float]:
        # Deterministic fallback embeddings keep retrieval operational if model load fails.
        import hashlib

        vec = [0.0] * self.vector_size
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % self.vector_size
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = sum(x * x for x in vec) ** 0.5
        if norm == 0:
            return vec
        return [x / norm for x in vec]


_kb_singleton = QdrantKnowledgeBase()


def get_knowledge_base() -> QdrantKnowledgeBase:
    return _kb_singleton
