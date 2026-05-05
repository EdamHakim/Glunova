from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from psychology.schemas import CrisisEvent, TherapyMessageInput, TrendPoint
from psychology.storage import CrisisStore, SessionRecord, SessionStore, TrendStore


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.replace(tzinfo=None)
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


class PsqlSessionStore(SessionStore):
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    def create_session(self, record: SessionRecord) -> None:
        history = Jsonb(record.crisis_score_history or [])
        summary = Jsonb(record.session_summary_json) if record.session_summary_json is not None else None
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO psychology_psychologysession
                      (session_id, patient_id, preferred_language, started_at, ended_at, last_state,
                       crisis_score_history_json, session_summary_json, created_at)
                    VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, NOW() AT TIME ZONE 'utc')
                    """,
                    (
                        record.session_id,
                        record.patient_id,
                        record.preferred_language,
                        record.started_at,
                        record.ended_at,
                        record.last_state or "",
                        history,
                        summary,
                    ),
                )
            conn.commit()

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, session_id, patient_id, preferred_language, started_at, ended_at, last_state,
                           crisis_score_history_json, session_summary_json
                    FROM psychology_psychologysession
                    WHERE session_id = %s::uuid
                    """,
                    (session_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                cur.execute(
                    """
                    SELECT role, content, created_at, fusion_metadata
                    FROM psychology_psychologymessage
                    WHERE session_id = %s
                    ORDER BY created_at ASC, id ASC
                    """,
                    (row["id"],),
                )
                msg_rows = cur.fetchall()
        messages: list[TherapyMessageInput] = []
        for m in msg_rows:
            fusion = m.get("fusion_metadata")
            if isinstance(fusion, str):
                try:
                    fusion = json.loads(fusion)
                except json.JSONDecodeError:
                    fusion = None
            messages.append(
                TherapyMessageInput(
                    role=m["role"],
                    content=m["content"],
                    created_at=_parse_dt(m["created_at"]),
                    fusion_metadata=fusion if isinstance(fusion, dict) else None,
                )
            )
        hist = row.get("crisis_score_history_json") or []
        if not isinstance(hist, list):
            hist = []
        summary_raw = row.get("session_summary_json")
        summary_dict = summary_raw if isinstance(summary_raw, dict) else None
        return SessionRecord(
            session_id=str(row["session_id"]),
            patient_id=int(row["patient_id"]),
            preferred_language=str(row["preferred_language"]),
            started_at=_parse_dt(row["started_at"]),
            ended_at=_parse_dt(row["ended_at"]) if row.get("ended_at") else None,
            messages=messages,
            last_state=row["last_state"] or None,
            crisis_score_history=[float(x) for x in hist],
            session_summary_json=summary_dict,
        )

    def put_session(self, record: SessionRecord) -> None:
        history = Jsonb(record.crisis_score_history or [])
        summary = Jsonb(record.session_summary_json) if record.session_summary_json is not None else None
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE psychology_psychologysession
                    SET ended_at = %s, last_state = %s, crisis_score_history_json = %s, session_summary_json = COALESCE(%s, session_summary_json)
                    WHERE session_id = %s::uuid
                    RETURNING id
                    """,
                    (record.ended_at, record.last_state or "", history, summary, record.session_id),
                )
                pk_row = cur.fetchone()
                if pk_row is None:
                    conn.rollback()
                    return
                sid = pk_row[0]
                cur.execute("DELETE FROM psychology_psychologymessage WHERE session_id = %s", (sid,))
                for msg in record.messages:
                    cur.execute(
                        """
                        INSERT INTO psychology_psychologymessage (session_id, role, content, created_at, fusion_metadata)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            sid,
                            msg.role,
                            msg.content,
                            msg.created_at,
                            Jsonb(msg.fusion_metadata) if msg.fusion_metadata is not None else None,
                        ),
                    )
            conn.commit()


class PsqlTrendStore(TrendStore):
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    def append(self, patient_id: int, point: TrendPoint) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO psychology_psychologyemotionlog (patient_id, logged_at, distress_score, mental_state)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (patient_id, point.timestamp, point.distress_score, point.state.value),
                )
            conn.commit()

    def recent(self, patient_id: int, limit: int) -> list[TrendPoint]:
        from psychology.schemas import MentalState

        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT logged_at, distress_score, mental_state
                    FROM psychology_psychologyemotionlog
                    WHERE patient_id = %s
                    ORDER BY logged_at DESC
                    LIMIT %s
                    """,
                    (patient_id, limit),
                )
                rows = cur.fetchall()
        points = [
            TrendPoint(
                timestamp=_parse_dt(r["logged_at"]),
                distress_score=float(r["distress_score"]),
                state=MentalState(r["mental_state"]),
            )
            for r in reversed(rows)
        ]
        return points


class PsqlCrisisStore(CrisisStore):
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    def add(self, event: CrisisEvent) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO psychology_psychologycrisisevent (id, patient_id, session_id, probability, action_taken)
                    VALUES (%s::uuid, %s, (SELECT id FROM psychology_psychologysession WHERE session_id = %s::uuid), %s, %s)
                    """,
                    (event.id, event.patient_id, event.session_id, event.probability, event.action_taken),
                )
            conn.commit()

    def list(self, patient_id: int | None = None) -> list[CrisisEvent]:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if patient_id is None:
                    cur.execute(
                        """
                        SELECT ce.id::text AS id, ce.patient_id, COALESCE(s.session_id::text, '') AS session_id,
                               ce.probability, ce.action_taken, ce.created_at, ce.acknowledged_at
                        FROM psychology_psychologycrisisevent ce
                        LEFT JOIN psychology_psychologysession s ON ce.session_id = s.id
                        ORDER BY ce.created_at DESC
                        LIMIT 200
                        """
                    )
                else:
                    cur.execute(
                        """
                        SELECT ce.id::text AS id, ce.patient_id, COALESCE(s.session_id::text, '') AS session_id,
                               ce.probability, ce.action_taken, ce.created_at, ce.acknowledged_at
                        FROM psychology_psychologycrisisevent ce
                        LEFT JOIN psychology_psychologysession s ON ce.session_id = s.id
                        WHERE ce.patient_id = %s
                        ORDER BY ce.created_at DESC
                        LIMIT 200
                        """,
                        (patient_id,),
                    )
                rows = cur.fetchall()
        return [
            CrisisEvent(
                id=r["id"],
                patient_id=int(r["patient_id"]),
                session_id=r["session_id"] or "",
                probability=float(r["probability"]),
                action_taken=str(r["action_taken"]),
                created_at=_parse_dt(r["created_at"]),
                acknowledged_at=_parse_dt(r["acknowledged_at"]) if r.get("acknowledged_at") else None,
            )
            for r in rows
        ]


def ensure_psychology_profile(pool: Any, patient_id: int) -> None:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO psychology_psychologyprofile
                  (user_id, health_context_json, personality_notes, preferred_language, physician_review_required,
                   semantic_profile_json, updated_at)
                VALUES (%s, '{}'::jsonb, '', 'en', false, '{}'::jsonb, NOW() AT TIME ZONE 'utc')
                ON CONFLICT (user_id) DO NOTHING
                """,
                (patient_id,),
            )
        conn.commit()


def get_physician_review_required(pool: Any, patient_id: int) -> bool:
    ensure_psychology_profile(pool, patient_id)
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT physician_review_required FROM psychology_psychologyprofile WHERE user_id = %s",
                (patient_id,),
            )
            row = cur.fetchone()
    if row is None:
        return False
    return bool(row[0])


def set_physician_review_required(pool: Any, patient_id: int, required: bool) -> None:
    ensure_psychology_profile(pool, patient_id)
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE psychology_psychologyprofile
                SET physician_review_required = %s, updated_at = NOW() AT TIME ZONE 'utc'
                WHERE user_id = %s
                """,
                (required, patient_id),
            )
        conn.commit()


def clear_physician_review_required(pool: Any, patient_id: int) -> None:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE psychology_psychologyprofile
                SET physician_review_required = false, updated_at = NOW() AT TIME ZONE 'utc'
                WHERE user_id = %s
                """,
                (patient_id,),
            )
        conn.commit()


def format_semantic_profile_compact(semantic: dict[str, Any] | None, *, max_chars: int = 900) -> str:
    """Token-safe bullet block for therapy prompts."""
    if not semantic or not isinstance(semantic, dict):
        return ""
    lines: list[str] = []

    def bullets(label: str, key: str) -> None:
        items = semantic.get(key)
        if isinstance(items, list) and items:
            short = [str(x).strip() for x in items[:6] if str(x).strip()]
            if short:
                lines.append(f"- {label}: {', '.join(short)}")

    bullets("Stressors", "primary_stressors")
    bullets("Triggers", "known_triggers")
    bullets("Coping strengths", "coping_strengths")
    bullets("Med notes (from sessions)", "current_medications_summary")

    for key, label in (
        ("communication_style", "Communication"),
        ("distress_trend_note", "Distress trend"),
        ("therapy_progress_note", "Therapy progress"),
        ("clinical_summary_note", "Clinical note"),
        ("therapy_language_note", "Language preference"),
    ):
        v = semantic.get(key)
        if isinstance(v, str) and v.strip():
            lines.append(f"- {label}: {v.strip()[:200]}")

    lc = semantic.get("last_crisis_at")
    if isinstance(lc, str) and lc.strip():
        lines.append(f"- Last crisis signal (recorded): {lc.strip()[:80]}")

    contradictions = semantic.get("contradictions_pending")
    if isinstance(contradictions, list) and contradictions:
        lines.append(f"- Open contradictions to reconcile: {len(contradictions)} item(s) (clinician may review)")

    out = "\n".join(lines)
    if len(out) > max_chars:
        return out[: max_chars - 3] + "..."
    return out


def get_semantic_profile_json(pool: Any, patient_id: int) -> dict[str, Any]:
    ensure_psychology_profile(pool, patient_id)
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT semantic_profile_json FROM psychology_psychologyprofile WHERE user_id = %s",
                (patient_id,),
            )
            row = cur.fetchone()
    if row is None:
        return {}
    raw = row.get("semantic_profile_json")
    return raw if isinstance(raw, dict) else {}


def set_semantic_profile_json(pool: Any, patient_id: int, data: dict[str, Any]) -> None:
    ensure_psychology_profile(pool, patient_id)
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE psychology_psychologyprofile
                SET semantic_profile_json = %s, updated_at = NOW() AT TIME ZONE 'utc'
                WHERE user_id = %s
                """,
                (Jsonb(data), patient_id),
            )
        conn.commit()


def count_completed_psychology_sessions(pool: Any, patient_id: int) -> int:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM psychology_psychologysession
                WHERE patient_id = %s AND ended_at IS NOT NULL
                """,
                (patient_id,),
            )
            row = cur.fetchone()
    if row is None:
        return 0
    return int(row[0])


def list_psychology_session_history(pool: Any, patient_id: int, limit: int) -> list[dict[str, Any]]:
    """Completed sessions only (`ended_at` set), newest first."""
    cap = max(1, min(int(limit), 60))
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT session_id::text AS session_id, patient_id, preferred_language,
                       started_at, ended_at, last_state, session_summary_json
                FROM psychology_psychologysession
                WHERE patient_id = %s AND ended_at IS NOT NULL
                ORDER BY ended_at DESC
                LIMIT %s
                """,
                (patient_id, cap),
            )
            rows = cur.fetchall()
    return list(rows)


def get_patient_health_context(pool: Any, patient_id: int) -> dict[str, Any]:
    ensure_psychology_profile(pool, patient_id)
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT health_context_json, personality_notes, preferred_language, semantic_profile_json
                FROM psychology_psychologyprofile WHERE user_id = %s
                """,
                (patient_id,),
            )
            row = cur.fetchone()
    if row is None:
        return {}
    hc = row.get("health_context_json") or {}
    if not isinstance(hc, dict):
        hc = {}
    sem = row.get("semantic_profile_json")
    sem_dict = sem if isinstance(sem, dict) else {}
    return {
        "health_context_json": hc,
        "personality_notes": str(row.get("personality_notes") or ""),
        "preferred_language": str(row.get("preferred_language") or "en"),
        "semantic_profile_compact": format_semantic_profile_compact(sem_dict),
        "semantic_profile_json": sem_dict,
    }


def acknowledge_crisis_event(pool: Any, event_id: str, patient_id: int | None) -> bool:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            if patient_id is None:
                cur.execute(
                    """
                    UPDATE psychology_psychologycrisisevent
                    SET acknowledged_at = NOW() AT TIME ZONE 'utc'
                    WHERE id = %s::uuid AND acknowledged_at IS NULL
                    """,
                    (event_id,),
                )
            else:
                cur.execute(
                    """
                    UPDATE psychology_psychologycrisisevent
                    SET acknowledged_at = NOW() AT TIME ZONE 'utc'
                    WHERE id = %s::uuid AND patient_id = %s AND acknowledged_at IS NULL
                    """,
                    (event_id, patient_id),
                )
            updated = cur.rowcount > 0
        conn.commit()
    return updated
