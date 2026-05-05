"""Nightly management command — trigger care coordination for all patients with active alerts.

Usage:
    python manage.py run_coordination_agent
    python manage.py run_coordination_agent --trigger nightly

Designed to be called by a cron job or Celery beat scheduler once per night.
"""

from __future__ import annotations

import logging

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Trigger the care coordination agent for all patients with active alerts in the last 24 hours."

    def add_arguments(self, parser):
        parser.add_argument(
            "--trigger",
            default="nightly",
            help="Trigger label sent to the agent (default: nightly)",
        )

    def handle(self, *args, **options):
        trigger = options["trigger"]
        ai_url = getattr(settings, "AI_SERVICE_URL", "http://127.0.0.1:8001").rstrip("/")
        url = f"{ai_url}/agent/coordinate/all"

        self.stdout.write(f"[run_coordination_agent] POST {url} trigger={trigger}")
        logger.info("[run_coordination_agent] POST %s trigger=%s", url, trigger)

        try:
            resp = httpx.post(url, json={"trigger": trigger}, timeout=120.0)
            resp.raise_for_status()
            data = resp.json()
            self.stdout.write(
                self.style.SUCCESS(
                    f"[run_coordination_agent] done — "
                    f"patients={data.get('patients_processed', '?')} "
                    f"dispatched={data.get('messages_dispatched', '?')} "
                    f"errors={data.get('errors', [])}"
                )
            )
        except httpx.HTTPStatusError as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"[run_coordination_agent] HTTP {exc.response.status_code}: {exc.response.text}"
                )
            )
            raise SystemExit(1)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"[run_coordination_agent] failed: {exc}"))
            raise SystemExit(1)
