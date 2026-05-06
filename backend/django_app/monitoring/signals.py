from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _fire_agent(patient_id: int) -> None:
    """Called in a daemon thread — POST to FastAPI agent endpoint, fire-and-forget."""
    try:
        import httpx

        ai_url = getattr(settings, "AI_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
        httpx.post(
            f"{ai_url}/agent/coordinate",
            json={"patient_id": patient_id, "trigger": "alert"},
            timeout=120.0,
        )
        logger.info("[monitoring.signals] Agent triggered for patient %s", patient_id)
    except Exception as exc:
        logger.warning("[monitoring.signals] Agent trigger failed for patient %s: %s", patient_id, exc)


def register() -> None:
    from monitoring.models import HealthAlert

    @receiver(post_save, sender=HealthAlert, dispatch_uid="glunova_critical_alert_agent")
    def on_critical_alert(sender, instance, created, **kwargs):
        if created and instance.severity == "CRITICAL":
            threading.Thread(
                target=_fire_agent,
                args=(instance.patient_id,),
                daemon=True,
            ).start()
