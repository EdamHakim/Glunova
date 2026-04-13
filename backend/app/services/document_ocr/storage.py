from __future__ import annotations

import shutil
from pathlib import Path
from uuid import UUID, uuid4

from app.core.config import settings


def ensure_upload_root() -> Path:
    root = settings.upload_path.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_upload(patient_id: UUID, file_bytes: bytes, original_name: str) -> str:
    """Returns relative storage path under UPLOAD_DIR."""
    root = ensure_upload_root()
    sub = root / str(patient_id)
    sub.mkdir(parents=True, exist_ok=True)
    safe_suffix = Path(original_name).suffix[:16] or ".bin"
    name = f"{uuid4().hex}{safe_suffix}"
    path = sub / name
    path.write_bytes(file_bytes)
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    return str(rel).replace("\\", "/")
