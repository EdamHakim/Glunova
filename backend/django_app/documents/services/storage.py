"""Upload to Supabase Storage when configured; otherwise Django default file storage."""

from __future__ import annotations

import logging
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def _supabase_configured() -> bool:
    url = (getattr(settings, "SUPABASE_URL", "") or "").strip()
    key = (getattr(settings, "SUPABASE_SERVICE_KEY", "") or "").strip()
    return bool(url and key)


def upload_medical_file(storage_path: str, data: bytes, content_type: str) -> None:
    if _supabase_configured():
        from supabase import create_client

        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        bucket = getattr(settings, "SUPABASE_STORAGE_BUCKET", "medical-documents")
        try:
            client.storage.from_(bucket).upload(
                storage_path,
                data,
                file_options={"content-type": content_type},
            )
        except Exception as exc:
            logger.exception("Supabase upload failed: %s", exc)
            raise
        return

    default_storage.save(storage_path, ContentFile(data))


def create_download_payload(storage_path: str) -> tuple[str, str]:
    """
    Returns (kind, value): ('redirect', signed_url) for Supabase,
    or ('django_storage', storage_path) for default_storage-backed files.
    """
    if _supabase_configured():
        from supabase import create_client

        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        bucket = getattr(settings, "SUPABASE_STORAGE_BUCKET", "medical-documents")
        signed = client.storage.from_(bucket).create_signed_url(storage_path, 60)
        url = signed.get("signedURL") or signed.get("signedUrl")
        if not url:
            raise RuntimeError("Could not create signed URL")
        return "redirect", url

    if not default_storage.exists(storage_path):
        raise FileNotFoundError(storage_path)
    return "django_storage", storage_path
