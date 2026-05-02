from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from core.config import settings
from psychology.memory_scoring import (
    MemoryScoreParams,
    cosine_hit_score,
    fuse_memory_scores,
    payload_age_days,
)
from psychology.storage import InMemoryMemoryStore, MemoryStore

logger = logging.getLogger(__name__)


def _memory_score_params() -> MemoryScoreParams:
    return MemoryScoreParams(
        decay_half_life_days=float(settings.psychology_memory_decay_half_life_days),
        decay_floor=float(settings.psychology_memory_decay_floor),
        clinical_boost=float(settings.psychology_memory_clinical_boost),
        recency_weight=float(settings.psychology_memory_recency_weight),
        recency_scale_days=float(settings.psychology_memory_recency_scale_days),
    )


class QdrantPatientMemoryStore(MemoryStore):
    """Per-patient episodic memory in Qdrant: vector search + temporal decay + clinical boost."""

    def __init__(self) -> None:
        self.enabled = bool(settings.qdrant_url and settings.qdrant_api_key)
        self.collection = settings.qdrant_collection_memory
        self._client = None
        self._kb_embed = None
        self._vector_size = settings.qdrant_vector_size
        if self.enabled:
            try:
                from qdrant_client import QdrantClient  # type: ignore

                self._client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
            except Exception as exc:
                logger.warning("Qdrant patient memory disabled: %s", exc)
                self.enabled = False

    def _attach_embedder(self) -> None:
        try:
            from psychology.knowledge_ingestion import get_knowledge_base

            kb = get_knowledge_base()
            self._kb_embed = kb
            self._vector_size = kb.vector_size
        except Exception:
            self._kb_embed = None

    def _ensure_collection(self) -> bool:
        if not self.enabled or self._client is None:
            return False
        try:
            from qdrant_client.models import Distance, VectorParams  # type: ignore

            if not self._client.collection_exists(collection_name=self.collection):
                self._client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(size=self._vector_size, distance=Distance.COSINE),
                )
            return True
        except Exception as exc:
            logger.warning("Patient memory collection ensure failed: %s", exc)
            return False

    def ensure_payload_indexes(self) -> None:
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
        for field_name, schema in (
            ("patient_id", PayloadSchemaType.INTEGER),
            ("session_id", PayloadSchemaType.KEYWORD),
            ("memory_type", PayloadSchemaType.KEYWORD),
            ("clinical_flag", PayloadSchemaType.BOOL),
        ):
            try:
                self._client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field_name,
                    field_schema=schema,
                )
            except Exception:
                logger.debug("patient memory index %s skipped", field_name, exc_info=True)

    def _vector(self, text: str) -> list[float]:
        if self._kb_embed is None:
            self._attach_embedder()
        if self._kb_embed is not None:
            return self._kb_embed._embed_text(text)  # noqa: SLF001
        return [0.0] * self._vector_size

    def append(self, patient_id: int, text: str, *, metadata: dict | None = None) -> None:
        if not self._ensure_collection() or self._client is None:
            return
        try:
            from qdrant_client.models import PointStruct  # type: ignore

            meta = dict(metadata) if isinstance(metadata, dict) else {}
            created = float(meta.get("created_at", time.time()))
            payload: dict[str, Any] = {
                "patient_id": patient_id,
                "text": text[:8000],
                "created_at": created,
            }
            for key in (
                "session_id",
                "session_number",
                "session_ended_at",
                "memory_type",
                "emotion_at_time",
                "distress_score",
                "clinical_flag",
                "superseded_by_session_id",
            ):
                if key in meta and meta[key] is not None:
                    payload[key] = meta[key]
            if isinstance(payload.get("clinical_flag"), str):
                payload["clinical_flag"] = payload["clinical_flag"].lower() in ("1", "true", "yes")
            pid = uuid.uuid4().int % (2**63)
            point = PointStruct(
                id=pid,
                vector=self._vector(text),
                payload=payload,
            )
            self._client.upsert(collection_name=self.collection, points=[point])
        except Exception as exc:
            logger.warning("Patient memory upsert failed: %s", exc)

    def top(self, patient_id: int, limit: int) -> list[str]:
        if not self._ensure_collection() or self._client is None:
            return []

        def _collect_rows(hit_payloads: list[dict[str, Any]]) -> list[tuple[float, str]]:
            rows: list[tuple[float, str]] = []
            for payload in hit_payloads:
                t = str(payload.get("text", "")).strip()
                if not t:
                    continue
                rows.append((float(payload.get("created_at", 0.0)), t))
            rows.sort(key=lambda x: x[0], reverse=True)
            return rows

        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue  # type: ignore

            flt = Filter(must=[FieldCondition(key="patient_id", match=MatchValue(value=patient_id))])
            hits, _next = self._client.scroll(
                collection_name=self.collection,
                scroll_filter=flt,
                limit=40,
                with_payload=True,
                with_vectors=False,
            )
            rows = _collect_rows([h.payload or {} for h in hits])
            return [t for _, t in rows[:limit]]
        except Exception as exc:
            message = str(exc)
            if "Index required but not found" not in message:
                logger.warning("Patient memory scroll failed: %s", exc)
                return []
            try:
                hits, _next = self._client.scroll(
                    collection_name=self.collection,
                    limit=max(80, limit * 12),
                    with_payload=True,
                    with_vectors=False,
                )
                fhits = [h.payload or {} for h in hits if int((h.payload or {}).get("patient_id", -1)) == patient_id]
                rows = _collect_rows(fhits)
                return [t for _, t in rows[:limit]]
            except Exception as fallback_exc:
                logger.warning("Patient memory fallback scroll failed: %s", fallback_exc)
                return []

    def search_by_message(
        self,
        patient_id: int,
        query_text: str,
        limit: int,
        *,
        recency_boost: bool = True,
    ) -> list[str]:
        q = (query_text or "").strip()
        if not q:
            return self.top(patient_id, limit)
        if not self._ensure_collection() or self._client is None:
            return []
        recall = max(int(settings.psychology_memory_recall_limit), limit * 3)
        query_vector = self._vector(q)

        hits: list[Any] = []
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue  # type: ignore

            flt = Filter(must=[FieldCondition(key="patient_id", match=MatchValue(value=patient_id))])
            if hasattr(self._client, "search"):
                hits = list(
                    self._client.search(
                        collection_name=self.collection,
                        query_vector=query_vector,
                        query_filter=flt,
                        limit=recall,
                        with_payload=True,
                    )
                )
            elif hasattr(self._client, "query_points"):
                result = self._client.query_points(
                    collection_name=self.collection,
                    query=query_vector,
                    query_filter=flt,
                    limit=recall,
                    with_payload=True,
                )
                points = getattr(result, "points", None)
                if isinstance(points, list):
                    hits = points
        except Exception as exc:
            if "Index required but not found" in str(exc):
                logger.warning("Patient memory filtered search unavailable; falling back to top(): %s", exc)
                return self.top(patient_id, limit)
            logger.warning("Patient memory search failed: %s", exc)
            return self.top(patient_id, limit)

        params = _memory_score_params()
        now_ts = time.time()
        scored: list[tuple[float, str]] = []
        for hit in hits:
            payload = hit.payload or {}
            if int(payload.get("patient_id", -1)) != patient_id:
                continue
            text = str(payload.get("text", "")).strip()
            if not text:
                continue
            similarity = cosine_hit_score(hit)
            age_d = payload_age_days(payload, now_ts=now_ts)
            clinical = bool(payload.get("clinical_flag", False))
            fuse = fuse_memory_scores(
                similarity,
                age_d,
                clinical_flag=clinical,
                params=params,
                recency_boost_enabled=recency_boost,
            )
            scored.append((fuse, text))

        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[str] = []
        seen: set[str] = set()
        for _, t in scored:
            if t in seen:
                continue
            seen.add(t)
            out.append(t)
            if len(out) >= limit:
                break
        if len(out) < limit:
            for t in self.top(patient_id, limit):
                if t not in seen:
                    seen.add(t)
                    out.append(t)
                if len(out) >= limit:
                    break
        return out[:limit]


class HybridMemoryStore(MemoryStore):
    def __init__(self, primary: MemoryStore, fallback: MemoryStore) -> None:
        self._primary = primary
        self._fallback = fallback

    def append(self, patient_id: int, text: str, *, metadata: dict | None = None) -> None:
        self._fallback.append(patient_id, text, metadata=metadata)
        self._primary.append(patient_id, text, metadata=metadata)

    def top(self, patient_id: int, limit: int) -> list[str]:
        got = self._primary.top(patient_id, limit)
        if got:
            return got
        return self._fallback.top(patient_id, limit)

    def search_by_message(
        self,
        patient_id: int,
        query_text: str,
        limit: int,
        *,
        recency_boost: bool = True,
    ) -> list[str]:
        got = self._primary.search_by_message(
            patient_id, query_text, limit, recency_boost=recency_boost
        )
        if got:
            return got
        return self._fallback.search_by_message(
            patient_id, query_text, limit, recency_boost=recency_boost
        )


def build_memory_store() -> MemoryStore:
    q = QdrantPatientMemoryStore()
    mem = InMemoryMemoryStore()
    if q.enabled:
        return HybridMemoryStore(q, mem)
    return mem
