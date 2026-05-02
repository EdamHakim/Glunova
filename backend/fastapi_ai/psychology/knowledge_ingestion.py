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
from psychology.chunking import chunk_manifest_stub, chunk_sanadi_kb_markdown
from psychology.kb_retrieval import coerce_mental_state_for_kb, preferred_sanadi_topics_for_mental_state
from psychology.schemas import MentalState
from psychology.pdf_kb import (
    SANADI_KB_MARKDOWN,
    resolve_psychology_data_dir,
    resolve_sanadi_kb_markdown_path,
    sanadi_kb_document_meta,
    stable_point_id,
)

logger = logging.getLogger(__name__)


def _coerce_int(raw: Any, *, default: int = -1) -> int:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
        return int(raw.strip())
    return default


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
        sanadi_md = resolve_sanadi_kb_markdown_path()
        if sanadi_md is not None:
            rel = sanadi_md.relative_to(root).as_posix()
            manifest.append(
                {
                    "name": "Sanadi Clinical Knowledge Base (markdown)",
                    "category": "sanadi_clinical_kb",
                    "url": f"local:{rel}",
                    "language": "en",
                    "notes": "Curated Sanadi RAG corpus: chunked and embedded from this file on reindex.",
                }
            )
        else:
            manifest.append(
                {
                    "name": "Sanadi Clinical Knowledge Base (markdown)",
                    "category": "sanadi_clinical_kb",
                    "url": "",
                    "language": "en",
                    "notes": (
                        f"No document KB indexed until `{SANADI_KB_MARKDOWN}` exists under the "
                        "configured psychology data directory."
                    ),
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
                if self._embedder is None and self._real_embeddings_enabled:
                    self._init_embedder()
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
        index_fields: list[tuple[str, Any]] = [
            ("sanadi_topic", PayloadSchemaType.KEYWORD),
            ("content_kind", PayloadSchemaType.KEYWORD),
            ("source_version", PayloadSchemaType.KEYWORD),
        ]
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

    def reindex_sources(self) -> dict[str, Any]:
        """
        Upsert manifest stubs plus chunks from `psychology data/sanadi_knowledge_base.md`.

        Reads UTF-8 markdown and embeds section-aligned chunks. If the file is absent, only
        manifest stubs are indexed (log warning). IO errors propagate.
        """
        empty: dict[str, Any] = {
            "indexed_chunks": 0,
            "manifest_chunks": 0,
            "pdf_chunks": 0,
            "pdf_files_seen": 0,
            "pdf_files_indexed": 0,
            "sanadi_md_chunks": 0,
            "sanadi_kb_markdown_used": False,
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
            sanadi_md_chunks = 0
            sanadi_kb_markdown_used = False
            data_root = resolve_psychology_data_dir()
            sanadi_path = resolve_sanadi_kb_markdown_path()
            if sanadi_path is not None and data_root is not None:
                raw_md = sanadi_path.read_text(encoding="utf-8")
                if raw_md.strip():
                    sanadi_kb_markdown_used = True
                    rel = sanadi_path.relative_to(data_root).as_posix()
                    meta = sanadi_kb_document_meta(rel)
                    for item in chunk_sanadi_kb_markdown(
                        raw_md,
                        max_piece_chars=settings.psychology_kb_sanadi_max_section_chars,
                        markdown_pack_size=settings.psychology_kb_sanadi_markdown_pack_chars,
                    ):
                        chunk = str(item.get("text", "")).strip()
                        if not chunk:
                            continue
                        cid = str(item.get("chunk_id", "") or "").strip()
                        sec_idx = item.get("section_index")
                        topic_raw = item.get("sanadi_topic")
                        payload = {
                            **meta,
                            "text": chunk,
                            "chunk_id": cid,
                            "content_kind": "sanadi_preamble" if cid == "SANADI_PREAMBLE" else "sanadi_section",
                            "sanadi_topic": str(topic_raw).strip()
                            if topic_raw is not None and str(topic_raw).strip()
                            else "general",
                            "section_index": _coerce_int(sec_idx, default=-1),
                        }
                        st = item.get("section_title")
                        if isinstance(st, str) and st.strip():
                            payload["section_title"] = st.strip()
                        pdf_points.append(
                            PointStruct(
                                id=stable_point_id("sanadi_md", rel, cid, chunk),
                                vector=self._embed_text(chunk),
                                payload={**payload, **_payload_freshness_fields()},
                            )
                        )
                        sanadi_md_chunks += 1
                    if sanadi_md_chunks:
                        pdf_files_indexed = 1
                else:
                    logger.warning("Sanadi KB markdown is empty: %s", sanadi_path)
            elif data_root is not None:
                logger.warning(
                    "Sanadi KB markdown not found under psychology data dir "
                    "(expected `%s`): document KB not reindexed; manifest stubs only.",
                    SANADI_KB_MARKDOWN,
                )

            all_points = manifest_points + pdf_points
            if all_points:
                self._client.upsert(collection_name=self.collection, points=all_points)
            _maybe_write_reindex_audit(len(all_points))

            return {
                "indexed_chunks": len(all_points),
                "manifest_chunks": len(manifest_points),
                "pdf_chunks": len(pdf_points),
                "pdf_files_seen": 1 if sanadi_kb_markdown_used else 0,
                "pdf_files_indexed": pdf_files_indexed,
                "sanadi_md_chunks": sanadi_md_chunks,
                "sanadi_kb_markdown_used": sanadi_kb_markdown_used,
                "sanadi_kb_file": SANADI_KB_MARKDOWN if sanadi_kb_markdown_used else None,
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
        if cat in {"ada_guidelines", "distress_scales", "sanadi_clinical_kb"}:
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

    def _rerank_hits(
        self,
        query: str,
        hits: list[Any],
        final_limit: int,
        *,
        mental_state_normalized: MentalState | None = None,
    ) -> list[dict[str, Any]]:
        w_vec = settings.psychology_kb_rerank_vector_weight
        w_lex = settings.psychology_kb_rerank_lexical_weight
        w_cat = settings.psychology_kb_rerank_category_weight
        q_tokens = self._tokenize(query)
        preferred_topics = preferred_sanadi_topics_for_mental_state(mental_state_normalized)
        topic_boost = settings.psychology_kb_mental_state_topic_boost
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
            ck = str(payload.get("content_kind") or "").strip()
            if ck == "manifest_stub":
                score *= settings.psychology_kb_manifest_stub_rerank_multiplier
            if preferred_topics:
                sanadi_topic = str(payload.get("sanadi_topic") or "").strip()
                if sanadi_topic and sanadi_topic in preferred_topics:
                    score *= topic_boost
            if str(payload.get("chunk_id")) == "SANADI_PREAMBLE" or ck == "sanadi_preamble":
                score *= settings.psychology_kb_preamble_rerank_multiplier
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
                    "sanadi_topic": str(payload.get("sanadi_topic", "")),
                    "section_index": _coerce_int(payload.get("section_index"), default=-1),
                    "content_kind": str(payload.get("content_kind", "")),
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
        mental_state: MentalState | str | None = None,
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
            ms_norm = coerce_mental_state_for_kb(mental_state)
            return self._rerank_hits(query, hits, final_limit, mental_state_normalized=ms_norm)
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
                "manifest_stub_multiplier": settings.psychology_kb_manifest_stub_rerank_multiplier,
                "mental_state_topic_boost": settings.psychology_kb_mental_state_topic_boost,
            },
            "retrieval_bounds": {
                "recall_floor": settings.psychology_kb_recall_limit,
                "final_cap": settings.psychology_kb_final_limit_cap,
                "session_limit_min": settings.psychology_kb_limit_min,
                "session_limit_max": settings.psychology_kb_limit_max,
            },
            "sanadi_chunking": {
                "max_section_chars": settings.psychology_kb_sanadi_max_section_chars,
                "markdown_pack_chars": settings.psychology_kb_sanadi_markdown_pack_chars,
                "preamble_rerank_multiplier": settings.psychology_kb_preamble_rerank_multiplier,
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
