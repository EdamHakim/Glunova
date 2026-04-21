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
    def append(self, patient_id: int, text: str) -> None: ...
    def top(self, patient_id: int, limit: int) -> list[str]: ...


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

    def append(self, patient_id: int, text: str) -> None:
        self._items.setdefault(patient_id, []).append(text)

    def top(self, patient_id: int, limit: int) -> list[str]:
        return self._items.get(patient_id, [])[-limit:]
