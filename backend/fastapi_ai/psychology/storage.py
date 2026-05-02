from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from psychology.schemas import CrisisEvent, TherapyMessageInput, TrendPoint


@dataclass
class SessionRecord:
    session_id: str
    patient_id: int
    preferred_language: str
    started_at: datetime
    ended_at: datetime | None = None
    messages: list[TherapyMessageInput] = field(default_factory=list)
    last_state: str | None = None
    crisis_score_history: list[float] = field(default_factory=list)
    session_summary_json: dict | None = None


class SessionStore(Protocol):
    def create_session(self, record: SessionRecord) -> None: ...
    def get_session(self, session_id: str) -> SessionRecord | None: ...
    def put_session(self, record: SessionRecord) -> None: ...


class TrendStore(Protocol):
    def append(self, patient_id: int, point: TrendPoint) -> None: ...
    def recent(self, patient_id: int, limit: int) -> list[TrendPoint]: ...


class CrisisStore(Protocol):
    def add(self, event: CrisisEvent) -> None: ...
    def list(self, patient_id: int | None = None) -> list[CrisisEvent]: ...


class MemoryStore(Protocol):
    def append(self, patient_id: int, text: str, *, metadata: dict | None = None) -> None: ...
    def top(self, patient_id: int, limit: int) -> list[str]: ...
    def search_by_message(
        self,
        patient_id: int,
        query_text: str,
        limit: int,
        *,
        recency_boost: bool = True,
    ) -> list[str]: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._items: dict[str, SessionRecord] = {}

    def create_session(self, record: SessionRecord) -> None:
        self._items[record.session_id] = record

    def get_session(self, session_id: str) -> SessionRecord | None:
        return self._items.get(session_id)

    def put_session(self, record: SessionRecord) -> None:
        self._items[record.session_id] = record


class InMemoryTrendStore:
    def __init__(self) -> None:
        self._items: dict[int, list[TrendPoint]] = {}

    def append(self, patient_id: int, point: TrendPoint) -> None:
        self._items.setdefault(patient_id, []).append(point)

    def recent(self, patient_id: int, limit: int) -> list[TrendPoint]:
        return self._items.get(patient_id, [])[-limit:]


class InMemoryCrisisStore:
    def __init__(self) -> None:
        self._items: list[CrisisEvent] = []

    def add(self, event: CrisisEvent) -> None:
        self._items.append(event)

    def list(self, patient_id: int | None = None) -> list[CrisisEvent]:
        if patient_id is None:
            return list(reversed(self._items))
        return [item for item in reversed(self._items) if item.patient_id == patient_id]


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._items: dict[int, list[str]] = {}

    def append(self, patient_id: int, text: str, *, metadata: dict | None = None) -> None:
        self._items.setdefault(patient_id, []).append(text)

    def top(self, patient_id: int, limit: int) -> list[str]:
        return self._items.get(patient_id, [])[-limit:]

    def search_by_message(
        self,
        patient_id: int,
        query_text: str,
        limit: int,
        *,
        recency_boost: bool = True,
    ) -> list[str]:
        """No vectors: naive keyword overlap rank, else tail recency."""
        items = self._items.get(patient_id, [])
        if not items or not (query_text or "").strip():
            return self.top(patient_id, limit)
        qtok = {t for t in _simple_tokens(query_text) if len(t) > 2}
        if not qtok:
            return self.top(patient_id, limit)
        ranked: list[tuple[int, str]] = []
        for t in items:
            ttok = _simple_tokens(t)
            overlap = sum(1 for w in ttok if w in qtok)
            ranked.append((overlap, t))
        ranked.sort(key=lambda x: (-x[0], -len(x[1])))
        out: list[str] = []
        seen: set[str] = set()
        for _score, blob in ranked:
            if blob in seen:
                continue
            seen.add(blob)
            out.append(blob)
            if len(out) >= limit:
                break
        if len(out) < limit:
            for t in reversed(items):
                if t not in seen:
                    seen.add(t)
                    out.append(t)
                if len(out) >= limit:
                    break
        return out[:limit]


def _simple_tokens(s: str) -> set[str]:
    raw = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in s.lower())
    return {w for w in raw.split() if w}
