#!/usr/bin/env python3
"""
Chunk + embed psychology KB into Qdrant (manifest stubs + sanadi_knowledge_base.md).

Usage (from repo):
  cd backend/fastapi_ai
  python scripts/embed_psychology_qdrant.py

Requires in environment / backend/.env:
  QDRANT_URL, QDRANT_API_KEY
  Optional: QDRANT_COLLECTION_CBT, PSYCHOLOGY_DATA_DIR (override KB folder)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_FASTAPI_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _FASTAPI_ROOT.parent

if str(_FASTAPI_ROOT) not in sys.path:
    sys.path.insert(0, str(_FASTAPI_ROOT))

from dotenv import load_dotenv

load_dotenv(_BACKEND_ROOT / ".env", override=True)

DRIFT_TOLERANCE = 0.55

SANADI_SECTION_IDS = {f"SANADI_S{i:02d}" for i in range(1, 29)}


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
    if not kb.ensure_collection():
        raise RuntimeError("Failed recreating Qdrant collection after reset")


def _keyword_any_match(text: str, probes: list[str]) -> bool:
    low = text.lower()
    return any(p.lower() in low for p in probes)


def _validate_sanadi_kb_pre_embed() -> dict[str, object]:
    from psychology.chunking import chunk_sanadi_kb_markdown
    from psychology.pdf_kb import SANADI_KB_MARKDOWN, resolve_sanadi_kb_markdown_path

    errors: list[str] = []
    sanadi_path = resolve_sanadi_kb_markdown_path()
    if sanadi_path is None:
        errors.append(
            f"{SANADI_KB_MARKDOWN} not found under psychology data directory "
            "(set PSYCHOLOGY_DATA_DIR or place the file in `<repo>/psychology data/`)."
        )
        return {
            "ingest_mode": "sanadi_kb_markdown",
            "files": [],
            "errors": errors,
        }

    raw = sanadi_path.read_text(encoding="utf-8")
    chunks = chunk_sanadi_kb_markdown(raw)
    by_id = {str(c.get("chunk_id")): str(c.get("text", "")) for c in chunks}
    present_sections = sorted(SANADI_SECTION_IDS.intersection(by_id.keys()))
    missing_sections = sorted(SANADI_SECTION_IDS.difference(by_id.keys()))
    if missing_sections:
        errors.append(f"{SANADI_KB_MARKDOWN}: missing section chunks: {missing_sections}")
    txt_s01 = by_id.get("SANADI_S01", "")
    if txt_s01 and not _keyword_any_match(txt_s01, ["diabetes distress", "distress"]):
        errors.append(f"{SANADI_KB_MARKDOWN}:SANADI_S01 failed keyword sanity check")
    if "SANADI_PREAMBLE" not in by_id:
        errors.append(f"{SANADI_KB_MARKDOWN}: missing SANADI_PREAMBLE chunk")

    entry = {
        "file": sanadi_path.name,
        "ingest_mode": "sanadi_kb_markdown",
        "section_chunks_found": len(present_sections),
        "chunk_ids": list(by_id.keys()),
        "chunk_stats": {
            cid: {"chars": len(txt), "preview": txt[:220].replace("\n", " ")}
            for cid, txt in by_id.items()
        },
    }

    baseline_path = _FASTAPI_ROOT / "tmp" / "psychology_embed_audit_baseline.json"
    if baseline_path.exists():
        try:
            prev = json.loads(baseline_path.read_text(encoding="utf-8"))
            pv = prev.get("validation") if isinstance(prev.get("validation"), dict) else {}
            if pv.get("ingest_mode") == "sanadi_kb_markdown":
                pfiles = pv.get("files") or []
                if isinstance(pfiles, list) and pfiles and isinstance(pfiles[0], dict):
                    prev_count = len(pfiles[0].get("chunk_ids") or [])
                    cur_count = len(by_id)
                    if prev_count > 0:
                        ratio = abs(cur_count - prev_count) / prev_count
                        if ratio > DRIFT_TOLERANCE:
                            errors.append(
                                f"{sanadi_path.name}: chunk-count drift too high "
                                f"({cur_count} vs {prev_count}, ratio={ratio:.2f})"
                            )
        except Exception:
            pass

    return {
        "ingest_mode": "sanadi_kb_markdown",
        "files": [entry],
        "errors": errors,
    }


def main() -> int:
    from psychology.knowledge_ingestion import get_knowledge_base

    parser = argparse.ArgumentParser(description="Embed Sanadi psychology KB into Qdrant")
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not clear old vectors before embedding",
    )
    parser.add_argument(
        "--skip-curated-validate",
        action="store_true",
        help="Skip fail-fast validation of sanadi_knowledge_base.md chunking",
    )
    parser.add_argument(
        "--audit-json",
        default="",
        help="Write extraction audit report JSON (default: backend/fastapi_ai/tmp/psychology_embed_audit.json)",
    )
    args = parser.parse_args()

    if not args.skip_curated_validate:
        print("Validating Sanadi markdown KB before embedding...", file=sys.stderr)
        report = _validate_sanadi_kb_pre_embed()
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
            print("Validation failed:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 4
        baseline_path = _FASTAPI_ROOT / "tmp" / "psychology_embed_audit_baseline.json"
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

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
    print("Reindexing (manifest + sanadi_knowledge_base.md)...", file=sys.stderr)
    stats = kb.reindex_sources()
    print(json.dumps(stats, indent=2))
    total = int(stats.get("indexed_chunks") or 0)
    if total == 0:
        print("Warning: 0 chunks upserted. Check Qdrant connectivity and logs.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
