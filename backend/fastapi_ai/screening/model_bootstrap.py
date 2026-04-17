"""Optional startup download of the tongue PyTorch checkpoint before routes import config paths."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)

_MIN_BYTES = 512 * 1024  # ignore tiny / corrupt files


def ensure_tongue_checkpoint() -> None:
    """
    If TONGUE_PT_MODEL_URL is set, download the file to TONGUE_PT_MODEL_PATH (default
    /tmp/glunova_models/resnet50_best.pt) unless that path already exists and looks valid.
    Sets TONGUE_PT_MODEL_PATH in the environment so screening.config picks it up on import.
    """
    url = os.environ.get("TONGUE_PT_MODEL_URL", "").strip()
    if not url:
        return

    default_target = Path("/tmp/glunova_models/resnet50_best.pt")
    raw_path = os.environ.get("TONGUE_PT_MODEL_PATH", "").strip()
    target = Path(raw_path).expanduser() if raw_path else default_target

    if target.exists() and target.is_file() and target.stat().st_size >= _MIN_BYTES:
        os.environ["TONGUE_PT_MODEL_PATH"] = str(target.resolve())
        log.info("Tongue checkpoint already present at %s", target)
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading tongue checkpoint from URL to %s", target)

    req = Request(url, headers={"User-Agent": "Glunova-FastAPI-model-bootstrap"})
    # URL comes from operator-controlled env (SAS / private artifact server).
    with urlopen(req, timeout=600) as resp:  # nosec B310
        body = resp.read()

    if len(body) < _MIN_BYTES:
        raise RuntimeError(
            f"Downloaded tongue model is too small ({len(body)} bytes); refusing to write."
        )

    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(body)
    tmp.replace(target)

    os.environ["TONGUE_PT_MODEL_PATH"] = str(target.resolve())
    log.info("Tongue checkpoint saved to %s", target)
