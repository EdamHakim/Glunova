from __future__ import annotations

import json
import logging
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
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


def _payload_freshness_fields() -> dict[str, Any]:
    return {
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "source_version": settings.psychology_kb_source_version,
    }


def _maybe_write_reindex_audit(indexed_chunks: int) -> None:
    try:
        audit_path = Path(__file__).resolve().parents[1] / "tmp" / "psychology_embed_audit.json"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(
            json.dumps(
                {
                    "last_reindex_at": datetime.now(timezone.utc).isoformat(),
                    "source_version": settings.psychology_kb_source_version,
                    "indexed_chunks": indexed_chunks,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        logger.debug("psychology KB reindex audit write skipped", exc_info=True)


class QdrantKnowledgeBase:
    def __init__(self) -> None:
        self.enabled = bool(settings.qdrant_url and settings.qdrant_api_key)
        self.collection = settings.qdrant_collection_cbt
        self.vector_size = settings.qdrant_vector_size
        self.embedding_model_name = settings.qdrant_embedding_model
        self._client = None
        self._embedder = None
        self._real_embeddings_enabled = True
        self._search_latencies_ms: deque[float] = deque(maxlen=200)
        if self.enabled:
            try:
                from qdrant_client import QdrantClient  # type: ignore

                self._client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
            except Exception:
                self.enabled = False

    def _init_embedder(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._embedder = SentenceTransformer(self.embedding_model_name)
            get_dim = getattr(self._embedder, "get_embedding_dimension", None)
            if not callable(get_dim):
                get_dim = getattr(self._embedder, "get_sentence_embedding_dimension", lambda: None)
            dim = get_dim()
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

    def ensure_payload_indexes(self) -> None:
        """Ensure payload indexes exist for filtered KB search (avoids slow unfiltered retries)."""
        if not self.enabled or self._client is None:
            return
        try:
            if not self._client.collection_exists(collection_name=self.collection):
                return
        except Exception:
            return
        try:
            from qdrant_client.models import PayloadSchemaType  # type: ignore[import-untyped]
        except Exception:
            return
        index_fields = [("source_version", PayloadSchemaType.KEYWORD)]
        if not settings.psychology_kb_english_only:
            index_fields.insert(0, ("language", PayloadSchemaType.KEYWORD))
        for field_name, schema in index_fields:
            try:
                self._client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field_name,
                    field_schema=schema,
                )
            except Exception:
                logger.debug(
                    "KB payload index not created (%s.%s); may already exist",
                    self.collection,
                    field_name,
                    exc_info=True,
                )

    def reindex_sources(self, extractor: str = "pypdf") -> dict[str, Any]:
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
        if self._embedder is None and self._real_embeddings_enabled:
            # Initialize embedder early so collection size matches real embedding dimension.
            self._init_embedder()
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
                                **_payload_freshness_fields(),
                            },
                        )
                    )

            pdf_points: list[PointStruct] = []
            pdf_files_indexed = 0
            data_root = resolve_psychology_data_dir()
            pdf_paths = discover_pdf_files(data_root) if data_root is not None else []
            for pdf_path in pdf_paths:
                try:
                    raw_text = extract_pdf_text(pdf_path, extractor=extractor)
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
                        payload["language"] = str(payload.get("language") or "en")
                        extra_meta = item.get("metadata")
                        if isinstance(extra_meta, dict):
                            payload.update({k: v for k, v in extra_meta.items() if isinstance(v, (str, int, float, bool))})
                        pdf_points.append(
                            PointStruct(
                                id=stable_point_id("pdf_curated", meta["file_path"], payload["chunk_id"], chunk),
                                vector=self._embed_text(chunk),
                                payload={**payload, **_payload_freshness_fields()},
                            )
                        )
                        file_chunks += 1
                else:
                    for chunk in chunk_pdf_for_kb(raw_text):
                        payload = {**meta, "text": chunk, "language": str(meta.get("language") or "en")}
                        pdf_points.append(
                            PointStruct(
                                id=stable_point_id("pdf", meta["file_path"], chunk),
                                vector=self._embed_text(chunk),
                                payload={**payload, **_payload_freshness_fields()},
                            )
                        )
                        file_chunks += 1
                if file_chunks:
                    pdf_files_indexed += 1

            all_points = manifest_points + pdf_points
            if all_points:
                self._client.upsert(collection_name=self.collection, points=all_points)
            _maybe_write_reindex_audit(len(all_points))
            return {
                "indexed_chunks": len(all_points),
                "manifest_chunks": len(manifest_points),
                "pdf_chunks": len(pdf_points),
                "pdf_files_seen": len(pdf_paths),
                "pdf_files_indexed": pdf_files_indexed,
                "source_version": settings.psychology_kb_source_version,
            }
        except Exception as exc:
            logger.exception("Qdrant reindex failed: %s", exc)
            return empty

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]{3,}", text.lower()))

    @staticmethod
    def _dedupe_key(payload: dict[str, Any]) -> str:
        text = str(payload.get("text", "")).strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text[:300]

    @staticmethod
    def _category_priority(category: str) -> float:
        cat = category.lower()
        if cat in {"ada_guidelines", "distress_scales"}:
            return 0.08
        if cat in {"cbt_scripts", "french_clinical"}:
            return 0.05
        return 0.0

    @staticmethod
    def _kb_freshness_tag(payload: dict[str, Any]) -> str:
        expected = settings.psychology_kb_source_version.strip()
        sv = str(payload.get("source_version") or "").strip()
        if not sv:
            return "unknown"
        if expected and sv == expected:
            return "current"
        if expected:
            return "stale"
        return "unknown"

    def _rerank_hits(self, query: str, hits: list[Any], final_limit: int) -> list[dict[str, Any]]:
        w_vec = settings.psychology_kb_rerank_vector_weight
        w_lex = settings.psychology_kb_rerank_lexical_weight
        w_cat = settings.psychology_kb_rerank_category_weight
        q_tokens = self._tokenize(query)
        ranked: list[tuple[float, dict[str, Any]]] = []
        seen: set[str] = set()
        for hit in hits:
            payload = dict(hit.payload or {})
            text = str(payload.get("text", "")).strip()
            if not text:
                continue
            dedupe = self._dedupe_key(payload)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            d_tokens = self._tokenize(text)
            lexical = 0.0
            if q_tokens and d_tokens:
                lexical = len(q_tokens.intersection(d_tokens)) / max(1, len(q_tokens))
            # Qdrant similarity is our current neural relevance proxy.
            vector_score = float(getattr(hit, "score", 0.0) or 0.0)
            category = str(payload.get("category", ""))
            category_raw = self._category_priority(category)
            # Normalize category bonus to [0, 1] so weighted blend remains interpretable.
            category_norm = min(1.0, max(0.0, category_raw / 0.08))
            score = (w_vec * vector_score) + (w_lex * lexical) + (w_cat * category_norm)
            ranked.append((score, payload))
        ranked.sort(key=lambda x: x[0], reverse=True)
        out: list[dict[str, Any]] = []
        for score, payload in ranked[:final_limit]:
            out.append(
                {
                    "source": str(payload.get("source", "")),
                    "category": str(payload.get("category", "")),
                    "language": str(payload.get("language", "")),
                    "text": str(payload.get("text", "")),
                    "relevance_score": round(score, 6),
                    "chunk_id": str(payload.get("chunk_id", "")),
                    "ingested_at": str(payload.get("ingested_at", "")),
                    "source_version": str(payload.get("source_version", "")),
                    "kb_freshness": self._kb_freshness_tag(payload),
                }
            )
        return out

    def search(
        self,
        query: str,
        language: str | None = None,
        limit: int = 3,
        *,
        source_version: str | None = None,
        min_ingested_at_iso: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.enabled or self._client is None or not query.strip():
            return []
        started = time.perf_counter()
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue, Range  # type: ignore

            must: list[Any] = []
            if not settings.psychology_kb_english_only and language and language != "mixed":
                must.append(
                    Filter(
                        should=[
                            FieldCondition(key="language", match=MatchValue(value=language)),
                            FieldCondition(key="language", match=MatchValue(value="en")),
                        ]
                    )
                )
            if source_version and source_version.strip():
                must.append(FieldCondition(key="source_version", match=MatchValue(value=source_version.strip())))
            if min_ingested_at_iso and min_ingested_at_iso.strip():
                must.append(FieldCondition(key="ingested_at", range=Range(gte=min_ingested_at_iso.strip())))

            query_filter: Any = Filter(must=must) if must else None

            recall = max(settings.psychology_kb_recall_limit, limit * 4)
            query_vector = self._embed_text(query)
            target_dim = self._collection_vector_size() or len(query_vector)
            if target_dim > 0 and len(query_vector) != target_dim:
                # Keep retrieval alive for existing collections with older dimensions.
                query_vector = self._fallback_embed_text(query, size=target_dim)
            hits: list[Any] = []
            try:
                if hasattr(self._client, "search"):
                    # Legacy qdrant-client API.
                    hits = list(
                        self._client.search(
                            collection_name=self.collection,
                            query_vector=query_vector,
                            query_filter=query_filter,
                            limit=recall,
                            with_payload=True,
                        )
                    )
                elif hasattr(self._client, "query_points"):
                    # qdrant-client >=1.10 switched to query_points().
                    result = self._client.query_points(
                        collection_name=self.collection,
                        query=query_vector,
                        query_filter=query_filter,
                        limit=recall,
                        with_payload=True,
                    )
                    points = getattr(result, "points", None)
                    if isinstance(points, list):
                        hits = points
            except Exception as exc:
                # Some Qdrant clusters require a payload index for filtered search.
                # If language index is missing, retry without filter instead of failing closed.
                if query_filter is not None and "Index required but not found" in str(exc):
                    logger.warning(
                        "Qdrant filtered search unavailable (missing payload index); retrying without filters: %s",
                        exc,
                    )
                    if hasattr(self._client, "search"):
                        hits = list(
                            self._client.search(
                                collection_name=self.collection,
                                query_vector=query_vector,
                                limit=recall,
                                with_payload=True,
                            )
                        )
                    elif hasattr(self._client, "query_points"):
                        result = self._client.query_points(
                            collection_name=self.collection,
                            query=query_vector,
                            limit=recall,
                            with_payload=True,
                        )
                        points = getattr(result, "points", None)
                        if isinstance(points, list):
                            hits = points
                else:
                    raise
            cap = settings.psychology_kb_final_limit_cap
            final_limit = min(max(limit, 1), cap)
            return self._rerank_hits(query, hits, final_limit)
        except Exception:
            return []
        finally:
            self._search_latencies_ms.append((time.perf_counter() - started) * 1000.0)

    def health_status(self) -> dict[str, Any]:
        audit_path = Path(__file__).resolve().parents[1] / "tmp" / "psychology_embed_audit.json"
        last_ingestion_at: str | None = None
        if audit_path.exists():
            last_ingestion_at = datetime.fromtimestamp(audit_path.stat().st_mtime, tz=timezone.utc).isoformat()

        vector_count = 0
        if self.enabled and self._client is not None:
            try:
                info = self._client.get_collection(collection_name=self.collection)
                points = getattr(info, "points_count", 0) or 0
                vector_count = int(points)
            except Exception:
                vector_count = 0

        p50 = round(median(self._search_latencies_ms), 2) if self._search_latencies_ms else None
        return {
            "qdrant_enabled": self.enabled,
            "collection": self.collection,
            "collection_points": vector_count,
            "last_ingestion_timestamp": last_ingestion_at,
            "retrieval_latency_ms_p50": p50,
            "language_qdrant_filter_enabled": not settings.psychology_kb_english_only,
            "configured_source_version": settings.psychology_kb_source_version,
            "rerank_weights": {
                "vector": settings.psychology_kb_rerank_vector_weight,
                "lexical": settings.psychology_kb_rerank_lexical_weight,
                "category": settings.psychology_kb_rerank_category_weight,
            },
            "retrieval_bounds": {
                "recall_floor": settings.psychology_kb_recall_limit,
                "final_cap": settings.psychology_kb_final_limit_cap,
                "session_limit_min": settings.psychology_kb_limit_min,
                "session_limit_max": settings.psychology_kb_limit_max,
            },
        }

    def _embed_text(self, text: str) -> list[float]:
        if self._embedder is None and self._real_embeddings_enabled:
            # Lazy-load embedder to keep FastAPI startup fast.
            self._init_embedder()
        if self._embedder is not None and self._real_embeddings_enabled:
            try:
                emb = self._embedder.encode([text], normalize_embeddings=True)
                if hasattr(emb, "tolist"):
                    return emb[0].tolist()
                return list(emb[0])
            except Exception:
                self._real_embeddings_enabled = False
        return self._fallback_embed_text(text, size=self.vector_size)

    def _collection_vector_size(self) -> int | None:
        if not self.enabled or self._client is None:
            return None
        try:
            info = self._client.get_collection(collection_name=self.collection)
            config = getattr(info, "config", None)
            params = getattr(config, "params", None)
            vectors = getattr(params, "vectors", None)
            size = getattr(vectors, "size", None)
            if isinstance(size, int) and size > 0:
                return size
        except Exception:
            return None
        return None

    def _fallback_embed_text(self, text: str, size: int) -> list[float]:
        # Deterministic fallback embeddings keep retrieval operational if model load fails.
        import hashlib

        vec = [0.0] * max(1, int(size))
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % len(vec)
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = sum(x * x for x in vec) ** 0.5
        if norm == 0:
            return vec
        return [x / norm for x in vec]


_kb_singleton: QdrantKnowledgeBase | None = None


def get_knowledge_base() -> QdrantKnowledgeBase:
    global _kb_singleton
    if _kb_singleton is None:
        _kb_singleton = QdrantKnowledgeBase()
    return _kb_singleton
