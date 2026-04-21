from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from core.config import settings
from psychology.storage import InMemoryMemoryStore, MemoryStore

logger = logging.getLogger(__name__)


class QdrantPatientMemoryStore(MemoryStore):
    """Per-patient long-term memory in Qdrant (`patient_id` payload filter)."""

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

    def _vector(self, text: str) -> list[float]:
        if self._kb_embed is None:
            self._attach_embedder()
        if self._kb_embed is not None:
            return self._kb_embed._embed_text(text)  # noqa: SLF001
        return [0.0] * self._vector_size

    def append(self, patient_id: int, text: str) -> None:
        if not self._ensure_collection() or self._client is None:
            return
        try:
            from qdrant_client.models import PointStruct  # type: ignore

            pid = uuid.uuid4().int % (2**63)
            point = PointStruct(
                id=pid,
                vector=self._vector(text),
                payload={
                    "patient_id": patient_id,
                    "text": text[:8000],
                    "created_at": time.time(),
                },
            )
            self._client.upsert(collection_name=self.collection, points=[point])
        except Exception as exc:
            logger.warning("Patient memory upsert failed: %s", exc)

    def top(self, patient_id: int, limit: int) -> list[str]:
        if not self._ensure_collection() or self._client is None:
            return []
        def _collect_rows(hits: list[Any]) -> list[tuple[float, str]]:
            rows: list[tuple[float, str]] = []
            for h in hits:
                payload = h.payload or {}
                if int(payload.get("patient_id", -1)) != patient_id:
                    continue
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
            rows = _collect_rows(hits)
            return [t for _, t in rows[:limit]]
        except Exception as exc:
            message = str(exc)
            if "Index required but not found" not in message:
                logger.warning("Patient memory scroll failed: %s", exc)
                return []
            # Fallback when payload index is missing in Qdrant cluster:
            # fetch recent points and filter patient_id in application code.
            try:
                hits, _next = self._client.scroll(
                    collection_name=self.collection,
                    limit=max(80, limit * 12),
                    with_payload=True,
                    with_vectors=False,
                )
                rows = _collect_rows(hits)
                return [t for _, t in rows[:limit]]
            except Exception as fallback_exc:
                logger.warning("Patient memory fallback scroll failed: %s", fallback_exc)
                return []


class HybridMemoryStore(MemoryStore):
    def __init__(self, primary: MemoryStore, fallback: MemoryStore) -> None:
        self._primary = primary
        self._fallback = fallback

    def append(self, patient_id: int, text: str) -> None:
        self._fallback.append(patient_id, text)
        self._primary.append(patient_id, text)

    def top(self, patient_id: int, limit: int) -> list[str]:
        got = self._primary.top(patient_id, limit)
        if got:
            return got
        return self._fallback.top(patient_id, limit)


def build_memory_store() -> MemoryStore:
    q = QdrantPatientMemoryStore()
    mem = InMemoryMemoryStore()
    if q.enabled:
        return HybridMemoryStore(q, mem)
    return mem
