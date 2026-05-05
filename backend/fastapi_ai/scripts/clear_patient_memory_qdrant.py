#!/usr/bin/env python3
"""
Drop and recreate the Qdrant **patient episodic memory** collection (empty).

Uses the same collection name and vector size as `core.config` / `psychology/patient_memory.py`.

Usage (from repo):
  cd backend/fastapi_ai
  python scripts/clear_patient_memory_qdrant.py --yes

  # Preview only (no changes):
  python scripts/clear_patient_memory_qdrant.py --dry-run

Requires `backend/.env` (or env) with:
  QDRANT_URL, QDRANT_API_KEY
Optional: QDRANT_COLLECTION_MEMORY (default: patient_memory), QDRANT_VECTOR_SIZE (default: 384)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_FASTAPI_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _FASTAPI_ROOT.parent

if str(_FASTAPI_ROOT) not in sys.path:
    sys.path.insert(0, str(_FASTAPI_ROOT))

from dotenv import load_dotenv

load_dotenv(_BACKEND_ROOT / ".env", override=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear Qdrant patient_memory collection.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive reset (required unless --dry-run).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print collection name and point count only; do not modify Qdrant.",
    )
    args = parser.parse_args()

    from core.config import settings

    url = (settings.qdrant_url or "").strip()
    key = (settings.qdrant_api_key or "").strip()
    if not url or not key:
        print("error: QDRANT_URL and QDRANT_API_KEY must be set (e.g. in backend/.env)", file=sys.stderr)
        return 1

    collection = (settings.qdrant_collection_memory or "patient_memory").strip()
    vector_size = int(settings.qdrant_vector_size)

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
    except ImportError as exc:
        print("error: install qdrant-client (see backend/fastapi_ai/requirements.txt)", file=sys.stderr)
        print(exc, file=sys.stderr)
        return 1

    client = QdrantClient(url=url, api_key=key)

    exists = False
    try:
        exists = bool(client.collection_exists(collection_name=collection))
    except Exception as exc:
        print(f"error: could not reach Qdrant: {exc}", file=sys.stderr)
        return 1

    if not exists:
        print(f"Collection {collection!r} does not exist — nothing to clear.")
        if args.dry_run:
            return 0
        if not args.yes:
            print("Re-run with --yes to create an empty collection with the default schema.")
            return 0
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        _ensure_indexes(client, collection)
        print(f"Created empty collection {collection!r} (vector_size={vector_size}).")
        return 0

    count = 0
    try:
        count = int(client.count(collection_name=collection, exact=True).count)
    except Exception:
        pass

    print(f"Collection: {collection!r}")
    print(f"Approx. vectors (exact count): {count}")

    if args.dry_run:
        print("Dry run: no changes made.")
        return 0

    if not args.yes:
        print("Refusing to delete without --yes (this removes all episodic memory vectors).")
        return 2

    client.delete_collection(collection_name=collection)
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    _ensure_indexes(client, collection)
    print(f"Deleted and recreated empty collection {collection!r} (vector_size={vector_size}).")
    return 0


def _ensure_indexes(client: object, collection: str) -> None:
    """Match payload indexes from `QdrantPatientMemoryStore.ensure_payload_indexes`."""
    try:
        from qdrant_client.models import PayloadSchemaType
    except Exception:
        return
    for field_name, schema in (
        ("patient_id", PayloadSchemaType.INTEGER),
        ("session_id", PayloadSchemaType.KEYWORD),
        ("memory_type", PayloadSchemaType.KEYWORD),
        ("clinical_flag", PayloadSchemaType.BOOL),
    ):
        try:
            client.create_payload_index(
                collection_name=collection,
                field_name=field_name,
                field_schema=schema,
            )
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
