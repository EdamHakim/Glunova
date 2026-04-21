#!/usr/bin/env python3
"""
Chunk + embed psychology KB into Qdrant (manifest stubs + all PDFs under `psychology data/`).

Usage (from repo):
  cd backend/fastapi_ai
  python scripts/embed_psychology_qdrant.py

Requires in environment / backend/.env:
  QDRANT_URL, QDRANT_API_KEY
  Optional: QDRANT_COLLECTION_CBT, PSYCHOLOGY_DATA_DIR (override PDF folder)
"""

from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

_FASTAPI_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _FASTAPI_ROOT.parent

if str(_FASTAPI_ROOT) not in sys.path:
    sys.path.insert(0, str(_FASTAPI_ROOT))

from dotenv import load_dotenv

load_dotenv(_BACKEND_ROOT / ".env", override=True)


def _reset_collection(kb: object) -> None:
    client = getattr(kb, "_client", None)
    if client is None:
        raise RuntimeError("Qdrant client is not initialized")
    collection = getattr(kb, "collection", "")
    if not collection:
        raise RuntimeError("Qdrant collection name is missing")
    try:
        exists = client.collection_exists(collection_name=collection)
    except Exception as exc:
        raise RuntimeError(f"Failed checking collection existence: {exc}") from exc
    if exists:
        client.delete_collection(collection_name=collection)
    # Recreate using KB defaults (vector size + cosine distance).
    if not kb.ensure_collection():
        raise RuntimeError("Failed recreating Qdrant collection after reset")


def main() -> int:
    from psychology.knowledge_ingestion import get_knowledge_base

    parser = argparse.ArgumentParser(description="Embed psychology KB into Qdrant")
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not clear old vectors before embedding",
    )
    args = parser.parse_args()

    kb = get_knowledge_base()
    if not kb.enabled:
        print(
            "Qdrant is not configured (need QDRANT_URL and QDRANT_API_KEY). "
            "Check backend/.env.",
            file=sys.stderr,
        )
        return 1

    print(f"Collection: {kb.collection!r}", file=sys.stderr)
    if args.keep_existing:
        print("Keeping existing vectors (upsert mode).", file=sys.stderr)
    else:
        print("Resetting collection: removing old vectors first...", file=sys.stderr)
        try:
            _reset_collection(kb)
        except Exception as exc:
            print(f"Failed to reset collection: {exc}", file=sys.stderr)
            return 3
    print("Reindexing (manifest + local PDFs)...", file=sys.stderr)
    stats = kb.reindex_sources()
    print(json.dumps(stats, indent=2))
    total = int(stats.get("indexed_chunks") or 0)
    if total == 0:
        print("Warning: 0 chunks upserted. Check Qdrant connectivity and logs.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
