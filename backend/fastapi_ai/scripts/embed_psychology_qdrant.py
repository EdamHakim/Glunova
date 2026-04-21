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
from datetime import datetime, timezone

_FASTAPI_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _FASTAPI_ROOT.parent

if str(_FASTAPI_ROOT) not in sys.path:
    sys.path.insert(0, str(_FASTAPI_ROOT))

from dotenv import load_dotenv

load_dotenv(_BACKEND_ROOT / ".env", override=True)

EXPECTED_CHUNKS: dict[str, dict[str, object]] = {
    "diabetes-ditress-screening-scale.pdf": {
        "required_ids": {"DDS_01", "DDS_02", "DDS_03"},
        "guards": {
            "DDS_01": {"min_chars": 1200, "keywords_any": ["q1", "q17"]},
            "DDS_02": {"min_chars": 250, "keywords_any": ["dds17 yields", "score", "mean item"]},
            "DDS_03": {"min_chars": 120, "keywords_any": ["emotional burden", "physician distress", "interpersonal distress"]},
        },
    },
    "ada_mental_health_toolkit_questionnaires.pdf": {
        "required_ids": {"ADA_TK_01", "ADA_TK_02", "ADA_TK_03", "ADA_TK_04", "ADA_TK_05"},
        "guards": {
            "ADA_TK_01": {"min_chars": 400, "keywords_any": ["paid", "problem areas in diabetes"]},
            "ADA_TK_02": {"min_chars": 100, "keywords_any": ["scoring", "paid"]},
            "ADA_TK_03": {"min_chars": 180, "keywords_any": ["phq-9", "depression"]},
            "ADA_TK_04": {"min_chars": 160, "keywords_any": ["gad-7", "anxiety"]},
            "ADA_TK_05": {"min_chars": 80, "keywords_any": ["diabetes and emotional health guide"]},
        },
    },
    "full section 5, open access on pmc.pdf": {
        "required_ids": {"ADA_S5_01", "ADA_S5_02", "ADA_S5_03", "ADA_S5_04", "ADA_S5_05", "ADA_S5_06"},
        "guards": {
            "ADA_S5_01": {"min_chars": 180, "keywords_any": ["psychosocial care", "5.45", "5.46", "5.47"]},
            "ADA_S5_02": {"min_chars": 160, "keywords_any": ["diabetes distress", "5.48"]},
            "ADA_S5_03": {"min_chars": 160, "keywords_any": ["depression", "5.51", "5.52", "5.53"]},
            "ADA_S5_04": {"min_chars": 120, "keywords_any": ["anxiety", "fear of hypoglycemia", "5.49", "5.50"]},
            "ADA_S5_05": {"min_chars": 90, "keywords_any": ["disordered eating"]},
            "ADA_S5_06": {"min_chars": 90, "keywords_any": ["referral", "mental health"]},
        },
    },
}


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


def _keyword_any_match(text: str, probes: list[str]) -> bool:
    low = text.lower()
    return any(p.lower() in low for p in probes)


def _validate_curated_chunks(extractor: str = "pypdf") -> dict[str, object]:
    from psychology.curated_kb import curated_chunks_for_pdf
    from psychology.pdf_kb import discover_pdf_files, extract_pdf_text, resolve_psychology_data_dir

    root = resolve_psychology_data_dir()
    if root is None:
        raise RuntimeError("Psychology data folder not found")
    files = discover_pdf_files(root)
    audit_files: list[dict[str, object]] = []
    errors: list[str] = []

    for path in files:
        name = path.name.lower()
        raw = extract_pdf_text(path, extractor=extractor)
        chunks = curated_chunks_for_pdf(path.name, raw)
        by_id = {str(c.get("chunk_id")): str(c.get("text", "")) for c in chunks}
        entry: dict[str, object] = {
            "file": path.name,
            "chunk_ids": list(by_id.keys()),
            "chunk_stats": {
                cid: {"chars": len(txt), "preview": txt[:220].replace("\n", " ")}
                for cid, txt in by_id.items()
            },
        }

        spec = EXPECTED_CHUNKS.get(name)
        if spec:
            required = set(spec.get("required_ids", set()))
            missing = sorted(required.difference(by_id.keys()))
            if missing:
                errors.append(f"{path.name}: missing required chunk IDs: {missing}")
            guards = spec.get("guards", {})
            if isinstance(guards, dict):
                for cid, guard_raw in guards.items():
                    txt = by_id.get(cid, "")
                    if not txt:
                        continue
                    if not isinstance(guard_raw, dict):
                        continue
                    min_chars = int(guard_raw.get("min_chars", 0))
                    if len(txt) < min_chars:
                        errors.append(f"{path.name}:{cid} too short ({len(txt)} < {min_chars})")
                    probes = guard_raw.get("keywords_any", [])
                    if isinstance(probes, list) and probes and not _keyword_any_match(txt, [str(p) for p in probes]):
                        errors.append(f"{path.name}:{cid} failed keyword guard {probes}")
        audit_files.append(entry)

    return {"files": audit_files, "errors": errors}


def main() -> int:
    from psychology.knowledge_ingestion import get_knowledge_base

    parser = argparse.ArgumentParser(description="Embed psychology KB into Qdrant")
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not clear old vectors before embedding",
    )
    parser.add_argument(
        "--skip-curated-validate",
        action="store_true",
        help="Skip fail-fast validation for curated chunk IDs/guards",
    )
    parser.add_argument(
        "--audit-json",
        default="",
        help="Write extraction audit report JSON (default: backend/fastapi_ai/tmp/psychology_embed_audit.json)",
    )
    parser.add_argument(
        "--extractor",
        default="pypdf",
        choices=("pypdf", "chonkie"),
        help="PDF extraction backend to use before chunking",
    )
    args = parser.parse_args()

    if not args.skip_curated_validate:
        print("Validating curated extraction before embedding...", file=sys.stderr)
        report = _validate_curated_chunks(extractor=args.extractor)
        out_path = Path(args.audit_json) if args.audit_json else (_FASTAPI_ROOT / "tmp" / "psychology_embed_audit.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "validation": report,
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Audit report written: {out_path}", file=sys.stderr)
        errors = report.get("errors", [])
        if isinstance(errors, list) and errors:
            print("Curated validation failed:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 4

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
    stats = kb.reindex_sources(extractor=args.extractor)
    print(json.dumps(stats, indent=2))
    total = int(stats.get("indexed_chunks") or 0)
    if total == 0:
        print("Warning: 0 chunks upserted. Check Qdrant connectivity and logs.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
