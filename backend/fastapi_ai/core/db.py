from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from core.config import settings

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

_pool: "ConnectionPool | None" = None
_pool_failed = False


def normalize_postgres_conninfo(url: str) -> str:
    """Strip SQLAlchemy dialect prefix + escape raw % in passwords for psycopg."""
    cleaned = url.strip()
    cleaned = re.sub(r"^postgresql\+psycopg(?:2|3)?://", "postgresql://", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^postgres\+psycopg(?:2|3)?://", "postgres://", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"%(?![0-9A-Fa-f]{2})", "%25", cleaned)
    return cleaned


def get_connection_pool() -> "ConnectionPool | None":
    """Shared lazy psycopg pool against Supabase. Returns None on failure (graceful)."""
    global _pool, _pool_failed
    if _pool_failed:
        return None
    if _pool is not None:
        return _pool
    try:
        from psycopg_pool import ConnectionPool
    except ImportError:
        logger.warning("psycopg_pool not installed; shared DB persistence disabled")
        _pool_failed = True
        return None
    conninfo = normalize_postgres_conninfo(settings.database_url)
    try:
        # prepare_threshold=None: Supabase pgBouncer rejects server-side prepared statements.
        _pool = ConnectionPool(
            conninfo=conninfo,
            min_size=1,
            max_size=8,
            kwargs={"prepare_threshold": None},
        )
        logger.info("Shared PostgreSQL pool initialized (Supabase)")
        return _pool
    except Exception as exc:
        logger.warning("Shared DB pool unavailable (%s)", exc)
        _pool_failed = True
        return None


def close_pool() -> None:
    global _pool
    if _pool is not None:
        try:
            _pool.close()
        except Exception:
            pass
        _pool = None
