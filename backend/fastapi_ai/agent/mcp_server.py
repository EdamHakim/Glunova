"""Glunova Care Coordination MCP server (stdio transport).

Run standalone:  python mcp_server.py
Spawned by:      agent/agents/context_agent.py and agent/agents/dispatch_agent.py
                 via StdioServerParameters inside an MCP ClientSession.

Tools exposed:
  get_monitoring_summary   — latest risk, alerts, disease trends
  get_nutrition_summary    — wellness plan adherence, nutrition goals
  get_psychology_state     — emotion assessment, therapy history
  get_care_team            — linked doctor + accepted caregivers
  dispatch_update          — write FamilyUpdate record to Django DB
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

# Ensure fastapi_ai/ is on the path when run as a subprocess.
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("glunova-care-coordinator")


# ── DB helper ─────────────────────────────────────────────────────────────────

def _conninfo() -> str:
    from core.config import settings
    from core.db import normalize_postgres_conninfo
    return normalize_postgres_conninfo(settings.database_url)


def _conn():
    import psycopg
    return psycopg.connect(_conninfo())


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _week_start() -> str:
    today = _now_utc().date()
    monday = today - timedelta(days=today.weekday())
    return str(monday)


# ── Tool 1: Monitoring ────────────────────────────────────────────────────────

@mcp.tool()
def get_monitoring_summary(
    patient_id: Annotated[int, "The patient's user ID"],
) -> str:
    """Return the latest risk assessment, active health alerts, and disease progression trends for a patient."""
    result: dict = {"patient_id": patient_id, "risk": None, "alerts": [], "progressions": []}
    try:
        with _conn() as conn:
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
                    result["risk"] = {
                        "tier": row[0], "score": row[1], "confidence": row[2],
                        "drivers": row[3], "assessed_at": str(row[4]),
                    }

                cur.execute(
                    """
                    SELECT title, message, severity, triggered_at
                    FROM monitoring_healthalert
                    WHERE patient_id = %s AND status = 'active'
                    ORDER BY triggered_at DESC
                    LIMIT 3
                    """,
                    (patient_id,),
                )
                result["alerts"] = [
                    {"title": r[0], "message": r[1], "severity": r[2], "triggered_at": str(r[3])}
                    for r in cur.fetchall()
                ]

                cur.execute(
                    """
                    SELECT DISTINCT ON (indicator) indicator, value, trend, recorded_at
                    FROM monitoring_diseaseprogression
                    WHERE patient_id = %s
                    ORDER BY indicator, recorded_at DESC
                    """,
                    (patient_id,),
                )
                result["progressions"] = [
                    {"indicator": r[0], "value": r[1], "trend": r[2], "recorded_at": str(r[3])}
                    for r in cur.fetchall()
                ]
    except Exception as exc:
        result["error"] = str(exc)
    return json.dumps(result)


# ── Tool 2: Nutrition ─────────────────────────────────────────────────────────

@mcp.tool()
def get_nutrition_summary(
    patient_id: Annotated[int, "The patient's user ID"],
) -> str:
    """Return the patient's current weekly wellness plan status, skipped exercise sessions, and active nutrition goal."""
    result: dict = {"patient_id": patient_id, "plan": None, "skipped_sessions": 0, "goal": None}
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                week = _week_start()
                cur.execute(
                    """
                    SELECT status, fitness_level, goal, week_start, clinical_snapshot
                    FROM nutrition_weeklywellnessplan
                    WHERE patient_id = %s AND week_start >= %s::date - INTERVAL '7 days'
                    ORDER BY week_start DESC
                    LIMIT 1
                    """,
                    (patient_id, week),
                )
                row = cur.fetchone()
                if row:
                    result["plan"] = {
                        "status": row[0], "fitness_level": row[1],
                        "goal": row[2], "week_start": str(row[3]),
                        "last_agent_run": (row[4] or {}).get("last_agent_run"),
                    }

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM nutrition_exercisesession
                    WHERE patient_id = %s AND status = 'skipped'
                      AND scheduled_for >= NOW() - INTERVAL '7 days'
                    """,
                    (patient_id,),
                )
                result["skipped_sessions"] = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT target_calories_kcal, target_carbs_g, target_protein_g
                    FROM nutrition_nutritiongoal
                    WHERE patient_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (patient_id,),
                )
                row = cur.fetchone()
                if row:
                    result["goal"] = {
                        "calories": row[0], "carbs_g": row[1], "protein_g": row[2],
                    }
    except Exception as exc:
        result["error"] = str(exc)
    return json.dumps(result)


# ── Tool 3: Psychology ────────────────────────────────────────────────────────

@mcp.tool()
def get_psychology_state(
    patient_id: Annotated[int, "The patient's user ID"],
) -> str:
    """Return the patient's latest emotion assessment, therapy session count in the last 7 days, and any open crisis events."""
    result: dict = {"patient_id": patient_id, "emotion": None, "sessions_7d": 0, "open_crisis": 0}
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT dominant_emotion, distress_level, summary, assessed_at
                    FROM psychology_emotionassessment
                    WHERE patient_id = %s
                    ORDER BY assessed_at DESC
                    LIMIT 1
                    """,
                    (patient_id,),
                )
                row = cur.fetchone()
                if row:
                    result["emotion"] = {
                        "dominant_emotion": row[0], "distress_level": row[1],
                        "summary": row[2], "assessed_at": str(row[3]),
                    }

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM psychology_therapysession
                    WHERE patient_id = %s AND started_at >= NOW() - INTERVAL '7 days'
                    """,
                    (patient_id,),
                )
                result["sessions_7d"] = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM psychology_psychologycrisisevent
                    WHERE patient_id = %s AND acknowledged_at IS NULL
                    """,
                    (patient_id,),
                )
                result["open_crisis"] = cur.fetchone()[0]
    except Exception as exc:
        result["error"] = str(exc)
    return json.dumps(result)


# ── Tool 4: Care team ─────────────────────────────────────────────────────────

@mcp.tool()
def get_care_team(
    patient_id: Annotated[int, "The patient's user ID"],
) -> str:
    """Return the patient's linked doctor and all accepted caregivers."""
    result: dict = {"patient_id": patient_id, "doctor": None, "caregivers": []}
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.id, u.first_name, u.last_name, u.username,
                           COALESCE(dp.specialization, '')
                    FROM users_patientdoctorlink pdl
                    JOIN users_user u ON pdl.doctor_id = u.id
                    LEFT JOIN users_doctorprofile dp ON dp.user_id = u.id
                    WHERE pdl.patient_id = %s
                    LIMIT 1
                    """,
                    (patient_id,),
                )
                row = cur.fetchone()
                if row:
                    name = f"{row[1]} {row[2]}".strip() or row[3]
                    result["doctor"] = {
                        "id": row[0], "name": name, "specialization": row[4],
                    }

                cur.execute(
                    """
                    SELECT u.id, u.first_name, u.last_name, u.username,
                           COALESCE(cp.relationship, '')
                    FROM documents_patientcaregiverlink pcl
                    JOIN users_user u ON pcl.caregiver_id = u.id
                    LEFT JOIN users_caregiverprofile cp ON cp.user_id = u.id
                    WHERE pcl.patient_id = %s AND pcl.status = 'accepted'
                    """,
                    (patient_id,),
                )
                result["caregivers"] = [
                    {"id": r[0], "name": f"{r[1]} {r[2]}".strip() or r[3], "relationship": r[4]}
                    for r in cur.fetchall()
                ]
    except Exception as exc:
        result["error"] = str(exc)
    return json.dumps(result)


# ── Tool 5: Dispatch ──────────────────────────────────────────────────────────

@mcp.tool()
def dispatch_update(
    patient_id: Annotated[int, "The patient's user ID"],
    recipient_type: Annotated[str, "One of: patient, caregiver, doctor"],
    message: Annotated[str, "The care coordination message to dispatch"],
    recipient_id: Annotated[int | None, "User ID of the caregiver or doctor. Omit for patient messages."] = None,
) -> str:
    """Write a care coordination update to the patient's care circle feed. Also stamps the current wellness plan with the agent run timestamp."""
    result: dict = {"ok": False, "family_update_id": None, "recipient_type": recipient_type}
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO carecircle_familyupdate
                        (patient_id, caregiver_id, summary, source, created_at)
                    VALUES (%s, %s, %s, 'agent', NOW())
                    RETURNING id
                    """,
                    (patient_id, recipient_id, message),
                )
                result["family_update_id"] = cur.fetchone()[0]

                # Stamp the current wellness plan for auditability.
                ts = _now_utc().isoformat()
                cur.execute(
                    """
                    UPDATE nutrition_weeklywellnessplan
                    SET clinical_snapshot = clinical_snapshot || %s::jsonb
                    WHERE patient_id = %s
                      AND id = (
                        SELECT id FROM nutrition_weeklywellnessplan
                        WHERE patient_id = %s
                        ORDER BY week_start DESC
                        LIMIT 1
                      )
                    """,
                    (
                        json.dumps({"last_agent_run": ts, "recipient_type": recipient_type}),
                        patient_id,
                        patient_id,
                    ),
                )
            conn.commit()
        result["ok"] = True
    except Exception as exc:
        result["error"] = str(exc)
    return json.dumps(result)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
