from contextlib import asynccontextmanager
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

# Same file as Django: backend/.env (Docker Compose also passes it via env_file).
_backend_root = Path(__file__).resolve().parent.parent
load_dotenv(_backend_root / ".env", override=True)

import os

from fastapi import FastAPI

_startup_log = logging.getLogger("fastapi_ai.startup")


def _warm_psychology_caches_sync() -> None:
    """Preload embeddings + indexes + local text pipelines so Sanadi's first message is responsive."""
    try:
        from psychology.knowledge_ingestion import get_knowledge_base

        kb = get_knowledge_base()
        if kb.enabled and kb._client is not None:
            try:
                if kb._client.collection_exists(collection_name=kb.collection):
                    kb.ensure_payload_indexes()
            except Exception:
                _startup_log.debug("psychology KB index ensure skipped", exc_info=True)
            try:
                kb.search("__warmup__", language=None, limit=1)
            except Exception:
                _startup_log.debug("psychology KB embed warm skipped", exc_info=True)

        try:
            from psychology.patient_memory import QdrantPatientMemoryStore

            mem = QdrantPatientMemoryStore()
            if mem.enabled and mem._client is not None:
                try:
                    if mem._client.collection_exists(collection_name=mem.collection):
                        mem.ensure_payload_indexes()
                except Exception:
                    _startup_log.debug("psychology patient memory index ensure skipped", exc_info=True)
        except Exception:
            _startup_log.debug("psychology patient memory warm skipped", exc_info=True)

        from psychology.router import service as psychology_service_instance

        psychology_service_instance.warm_heavy_psychology_caches()
    except Exception:
        _startup_log.debug("psychology cold-start warm aborted", exc_info=True)


from fastapi.middleware.cors import CORSMiddleware

from agent.router import router as agent_router
from clinic.router import router as clinic_router
from kids.router import router as kids_router
from monitoring.router import router as monitoring_router
from nutrition.router import router as nutrition_router
from psychology.router import router as psychology_router
from screening.router import router as screening_router
from extraction.router import router as extraction_router
from wellness.router import router as wellness_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(_warm_psychology_caches_sync)
    yield
    from psychology.db import close_pool as close_psychology_pool
    from core.db import close_pool as close_shared_pool

    close_psychology_pool()
    close_shared_pool()


app = FastAPI(title="Glunova AI Engine", lifespan=lifespan)

raw_origins = os.getenv("FRONTEND_ORIGINS", "")
frontend_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
legacy_origin = os.getenv("FRONTEND_ORIGIN", "").strip()
if legacy_origin:
    frontend_origins.append(legacy_origin)
if not frontend_origins:
    frontend_origins = ["http://localhost:3000", "http://172.19.32.1:3000"]
frontend_origins = list(dict.fromkeys(frontend_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    # Support local network frontend hosts (e.g. http://192.168.x.x:3000) in dev.
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}):3000$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router, prefix="/agent", tags=["agent"])
app.include_router(screening_router)
app.include_router(extraction_router)
app.include_router(clinic_router)
app.include_router(psychology_router)
app.include_router(nutrition_router)
app.include_router(wellness_router)
app.include_router(kids_router)
app.include_router(monitoring_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "fastapi_ai"}


@app.get("/health/psychology")
def health_psychology() -> dict:
    from psychology.db import get_connection_pool
    from psychology.knowledge_ingestion import get_knowledge_base

    pool = get_connection_pool()
    kb = get_knowledge_base()
    return {
        "postgres_pool": pool is not None,
        "qdrant_cbt": bool(getattr(kb, "enabled", False)),
    }
