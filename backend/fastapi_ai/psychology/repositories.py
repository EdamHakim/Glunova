from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from psychology.schemas import CrisisEvent, TherapyMessageInput, TrendPoint
from psychology.storage import CrisisStore, SessionRecord, SessionStore, TrendStore

logger = logging.getLogger(__name__)


def _fire_crisis_agent(patient_id: int) -> None:
    try:
        from agent.orchestrator import run_coordination
        asyncio.run(run_coordination(patient_id, "crisis"))
        logger.info("[psychology.repositories] Agent coordination completed for patient %s", patient_id)
    except Exception as exc:
        logger.warning("[psychology.repositories] Agent coordination failed for patient %s: %s", patient_id, exc)


def _fire_therapy_session_agent(patient_id: int) -> None:
    """Post–therapy care coordination: summaries to patient / caregivers / doctor."""
    try:
        from agent.orchestrator import run_coordination

        asyncio.run(run_coordination(int(patient_id), "therapy_session"))
        logger.info(
            "[psychology.repositories] Therapy-session coordination completed for patient %s",
            patient_id,
        )
    except Exception as exc:
        logger.warning(
            "[psychology.repositories] Therapy-session coordination failed for patient %s: %s",
            patient_id,
            exc,
        )


def spawn_therapy_session_coordination(patient_id: int) -> None:
    threading.Thread(target=_fire_therapy_session_agent, args=(patient_id,), daemon=True).start()


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
        threading.Thread(
            target=_fire_crisis_agent,
            args=(event.patient_id,),
            daemon=True,
        ).start()
        logger.info("[psychology.repositories] Agent thread spawned for crisis patient %s", event.patient_id)

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


def _week_start_monday_utc() -> date:
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=today.weekday())


def _integrated_care_compact(conn: Any, patient_id: int, *, max_chars: int = 780) -> str:
    """Token-safe summary of fusion risk, alerts, nutrition goal, meal/exercise adherence for therapy prompts."""
    lines: list[str] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tier, score, confidence, drivers, assessed_at
                FROM monitoring_riskassessment
                WHERE patient_id = %s
                ORDER BY assessed_at DESC
                LIMIT 1
                """,
                (patient_id,),
            )
            row = cur.fetchone()
            if row:
                tier = str(row[0] or "").strip().upper() or "UNKNOWN"
                score_v = row[1]
                conf_v = row[2]
                drivers_raw = row[3]
                assessed = row[4]
                score_s = f"{float(score_v):.2f}" if score_v is not None else "n/a"
                conf_s = f"{float(conf_v):.2f}" if conf_v is not None else "n/a"
                driver_bits: list[str] = []
                if isinstance(drivers_raw, list):
                    for d in drivers_raw[:4]:
                        if isinstance(d, str) and d.strip():
                            driver_bits.append(d.strip()[:80])
                        elif isinstance(d, dict):
                            label = str(d.get("label") or d.get("name") or d.get("modality") or "").strip()
                            if label:
                                driver_bits.append(label[:80])
                driver_txt = f"; drivers: {', '.join(driver_bits)}" if driver_bits else ""
                lines.append(
                    f"Diabetes monitoring: risk tier {tier} (score {score_s}, confidence {conf_s}){driver_txt}. "
                    f"Assessed: {assessed}."
                )

            cur.execute(
                """
                SELECT title, severity
                FROM monitoring_healthalert
                WHERE patient_id = %s AND status = 'active'
                ORDER BY triggered_at DESC
                LIMIT 3
                """,
                (patient_id,),
            )
            alert_rows = cur.fetchall()
            if alert_rows:
                bits = [f"{str(t[0])[:100]} ({str(t[1])})" for t in alert_rows]
                lines.append("Active alerts: " + "; ".join(bits) + ".")

            cur.execute(
                """
                SELECT DISTINCT ON (indicator) indicator, value, trend
                FROM monitoring_diseaseprogression
                WHERE patient_id = %s
                ORDER BY indicator, recorded_at DESC
                LIMIT 4
                """,
                (patient_id,),
            )
            prog = cur.fetchall()
            if prog:
                pb = []
                for ind, val, tr in prog:
                    pb.append(f"{str(ind)[:48]}={val} ({tr})")
                lines.append("Disease progression (latest): " + "; ".join(pb) + ".")

            ws = _week_start_monday_utc()
            cur.execute(
                """
                SELECT id, status, fitness_level, goal, week_start, clinical_snapshot
                FROM nutrition_weeklywellnessplan
                WHERE patient_id = %s AND week_start >= %s::date - INTERVAL '7 days'
                ORDER BY week_start DESC
                LIMIT 1
                """,
                (patient_id, str(ws)),
            )
            plan_row = cur.fetchone()
            plan_id: int | None = None
            if plan_row:
                plan_id_raw, st, fit, goal, wstart, snap = plan_row
                if plan_id_raw is not None:
                    plan_id = int(plan_id_raw)
                extra = ""
                if isinstance(snap, dict):
                    run = snap.get("last_agent_run")
                    if run:
                        extra = f" Last plan update: {str(run)[:80]}."
                lines.append(
                    f"Weekly wellness plan: status {st}, week_start {wstart}, goal {goal or '—'}, "
                    f"fitness_level {fit or '—'}.{extra}"
                )

            if plan_id is not None:
                cur.execute(
                    """
                    SELECT
                      COUNT(*) FILTER (WHERE status = 'completed') AS done_m,
                      COUNT(*) FILTER (WHERE status = 'skipped') AS skip_m
                    FROM nutrition_meal
                    WHERE wellness_plan_id = %s
                    """,
                    (plan_id,),
                )
                mrow = cur.fetchone()
                if mrow and (mrow[0] or mrow[1]):
                    lines.append(
                        f"Planned meals this week: {int(mrow[0] or 0)} completed, {int(mrow[1] or 0)} skipped."
                    )

            cur.execute(
                """
                SELECT target_calories_kcal, target_carbs_g, target_protein_g, target_fat_g
                FROM nutrition_nutritiongoal
                WHERE patient_id = %s
                ORDER BY valid_from DESC NULLS LAST, created_at DESC
                LIMIT 1
                """,
                (patient_id,),
            )
            g = cur.fetchone()
            if g:
                lines.append(
                    f"Nutrition targets (active goal): ~{int(g[0])} kcal/d, carbs {g[1]} g, protein {g[2]} g, fat {g[3]} g."
                )

            cur.execute(
                """
                SELECT
                  COUNT(*) FILTER (WHERE status = 'completed') AS done_e,
                  COUNT(*) FILTER (WHERE status = 'skipped') AS skip_e,
                  COUNT(*) FILTER (WHERE status = 'planned') AS plan_e
                FROM nutrition_exercisesession
                WHERE patient_id = %s AND scheduled_for >= NOW() - INTERVAL '7 days'
                """,
                (patient_id,),
            )
            ex = cur.fetchone()
            if ex and any(ex):
                lines.append(
                    f"Physical activity (7d): {int(ex[0] or 0)} completed, {int(ex[1] or 0)} skipped, "
                    f"{int(ex[2] or 0)} still planned."
                )
    except Exception as exc:
        logger.warning("integrated care context query failed for patient %s: %s", patient_id, exc)
        return ""

    out = " ".join(lines).strip()
    if len(out) > max_chars:
        return out[: max_chars - 3] + "..."
    return out


def get_patient_health_context(pool: Any, patient_id: int) -> dict[str, Any]:
    ensure_psychology_profile(pool, patient_id)
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT health_context_json, personality_notes, preferred_language, semantic_profile_json,
                       physician_review_required
                FROM psychology_psychologyprofile WHERE user_id = %s
                """,
                (patient_id,),
            )
            row = cur.fetchone()
        integrated = _integrated_care_compact(conn, patient_id)
    if row is None:
        return {}
    hc = row.get("health_context_json") or {}
    if not isinstance(hc, dict):
        hc = {}
    sem = row.get("semantic_profile_json")
    sem_dict = sem if isinstance(sem, dict) else {}
    extras: list[str] = []
    if integrated:
        extras.append(integrated)
    if bool(row.get("physician_review_required")):
        extras.append("Flag: clinician/physician review has been requested for this patient.")
    combined = " ".join(extras).strip()
    return {
        "health_context_json": hc,
        "personality_notes": str(row.get("personality_notes") or ""),
        "preferred_language": str(row.get("preferred_language") or "en"),
        "semantic_profile_compact": format_semantic_profile_compact(sem_dict),
        "semantic_profile_json": sem_dict,
        "integrated_care_compact": combined,
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
