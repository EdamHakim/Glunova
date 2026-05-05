"""Hugging Face Inference API helpers for psychology emotion modalities (remote inference, no local model weights)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)


def _hf_http_status(exc: BaseException) -> int | None:
    try:
        from huggingface_hub.utils import HfHubHTTPError

        if isinstance(exc, HfHubHTTPError) and getattr(exc, "response", None) is not None:
            code = getattr(exc.response, "status_code", None)
            return int(code) if code is not None else None
    except Exception:
        pass
    resp = getattr(exc, "response", None)
    if resp is not None:
        code = getattr(resp, "status_code", None)
        if code is not None:
            try:
                return int(code)
            except (TypeError, ValueError):
                pass
    return None


def _hf_inference_error_should_retry(exc: BaseException) -> bool:
    """429/5xx/408 may recover; most 4xx (e.g. 400 model not on provider) will not — avoid wasted retries."""
    status = _hf_http_status(exc)
    if status is not None:
        if status in (408, 429):
            return True
        if 400 <= status < 500:
            return False
        if status >= 500:
            return True
        return False
    low = str(exc).lower()
    if "model not supported" in low or "not supported by provider" in low:
        return False
    return True


def _inference_client(token: str, timeout_s: float) -> InferenceClient:
    """Build InferenceClient with stable routing for Hub models that have no third-party inference mapping."""
    raw = (os.getenv("PSYCHOLOGY_HF_INFERENCE_PROVIDER") or "").strip()
    if not raw:
        try:
            from core.config import settings

            raw = (getattr(settings, "psychology_hf_inference_provider", None) or "").strip()
        except Exception:
            raw = ""
    if not raw:
        raw = "auto"
    if raw.lower() == "auto":
        return InferenceClient(token=token.strip(), timeout=timeout_s)
    return InferenceClient(token=token.strip(), timeout=timeout_s, provider=raw)  # type: ignore[arg-type]


def _scalar_label_score(item: Any) -> tuple[str, float]:
    if item is None:
        return "neutral", 0.0
    if isinstance(item, dict):
        return str(item.get("label") or item.get("class") or "neutral"), float(item.get("score") or item.get("probability") or 0.0)
    label = getattr(item, "label", None)
    score = getattr(item, "score", None)
    return str(label or "neutral"), float(score or 0.0)


def _first_classification_item(ranked: Any) -> Any | None:
    """Normalize HF Inference `text_classification` output (list vs single element across hub versions)."""
    if ranked is None:
        return None
    if isinstance(ranked, (list, tuple)):
        return ranked[0] if ranked else None
    return ranked


def classify_image(api_token: str, model_id: str, image_bytes: bytes, timeout_s: float) -> tuple[str, float] | None:
    """Image classification via HF Inference (`image_classification` pipeline semantics)."""
    try:
        client = _inference_client(api_token, timeout_s)
        ranked = client.image_classification(image_bytes, model=model_id, top_k=1)
        if not ranked:
            return None
        label, score = _scalar_label_score(ranked[0])
        return label, score
    except Exception as exc:
        logger.warning("HF Inference image_classification failed for %s: %s", model_id, exc)
        return None


def classify_text(
    api_token: str,
    model_id: str,
    text: str,
    timeout_s: float,
    *,
    retries: int = 1,
    max_input_chars: int = 1024,
) -> tuple[str, float] | None:
    """Text classification (emotion labels) via HF Inference.

    Long inputs are truncated (many classifiers error past ~512 subword tokens).
    """
    trimmed = (text or "").strip()
    if max_input_chars > 0 and len(trimmed) > max_input_chars:
        trimmed = trimmed[:max_input_chars]

    token = api_token.strip()
    attempts = max(1, min(int(retries), 4))
    for attempt in range(attempts):
        try:
            client = _inference_client(token, timeout_s)
            ranked = client.text_classification(trimmed, model=model_id, top_k=1)
            item = _first_classification_item(ranked)
            if item is None:
                return None
            label, score = _scalar_label_score(item)
            return label, score
        except Exception as exc:
            last = attempt + 1 >= attempts or not _hf_inference_error_should_retry(exc)
            if last:
                logger.warning(
                    "HF Inference text_classification failed for %s after %s attempt(s): %s",
                    model_id,
                    attempt + 1,
                    exc,
                )
                return None
            time.sleep(0.2 * (attempt + 1))
    return None


def classify_audio(
    api_token: str,
    model_id: str,
    audio_bytes: bytes,
    timeout_s: float,
    *,
    retries: int = 1,
) -> tuple[str, float] | None:
    """Audio classification via HF Inference (`audio_classification`)."""
    if not audio_bytes:
        return None
    token = api_token.strip()
    attempts = max(1, min(int(retries), 4))
    for attempt in range(attempts):
        try:
            client = _inference_client(token, timeout_s)
            ranked = client.audio_classification(audio_bytes, model=model_id, top_k=1)
            if not ranked:
                return None
            label, score = _scalar_label_score(ranked[0])
            return label, score
        except Exception as exc:
            last = attempt + 1 >= attempts or not _hf_inference_error_should_retry(exc)
            if last:
                logger.warning(
                    "HF Inference audio_classification failed for %s after %s attempt(s): %s",
                    model_id,
                    attempt + 1,
                    exc,
                )
                return None
            time.sleep(0.2 * (attempt + 1))
    return None


def embed_text(api_token: str, model_id: str, text: str, timeout_s: float) -> list[float] | None:
    """Sentence embedding via HF Inference API (`feature_extraction`). Returns a normalised 1-D float list."""
    import math
    try:
        client = _inference_client(api_token, timeout_s)
        result = client.feature_extraction(text, model=model_id)
        # result may be np.ndarray with shape (1, dim) or (dim,)
        if hasattr(result, "tolist"):
            flat = result.tolist()
        else:
            flat = list(result)
        # Flatten [[...]] → [...]
        if flat and isinstance(flat[0], list):
            flat = flat[0]
        # L2-normalise to match sentence-transformers normalize_embeddings=True
        norm = math.sqrt(sum(x * x for x in flat)) or 1.0
        return [x / norm for x in flat]
    except Exception as exc:
        logger.warning("HF Inference feature_extraction failed for %s: %s", model_id, exc)
        return None
