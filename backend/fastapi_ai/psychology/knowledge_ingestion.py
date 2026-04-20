from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.config import settings


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

    def reindex_sources(self) -> int:
        if not self.ensure_collection() or self._client is None:
            return 0
        try:
            from qdrant_client.models import PointStruct  # type: ignore

            points: list[PointStruct] = []
            point_id = 1
            for source in SOURCES:
                content = f"{source.name}. {source.notes}. Source: {source.url}"
                for chunk in chunk_text(content):
                    vector = self._embed_text(chunk)
                    points.append(
                        PointStruct(
                            id=point_id,
                            vector=vector,
                            payload={
                                "source": source.name,
                                "category": source.category,
                                "url": source.url,
                                "language": source.language,
                                "text": chunk,
                            },
                        )
                    )
                    point_id += 1
            if points:
                self._client.upsert(collection_name=self.collection, points=points)
            return len(points)
        except Exception:
            return 0

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
