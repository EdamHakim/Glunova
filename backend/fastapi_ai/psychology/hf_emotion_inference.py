"""Hugging Face Inference API helpers for psychology emotion modalities (remote inference, no local model weights)."""

from __future__ import annotations

import logging
from typing import Any

from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)


def _scalar_label_score(item: Any) -> tuple[str, float]:
    if item is None:
        return "neutral", 0.0
    if isinstance(item, dict):
        return str(item.get("label") or item.get("class") or "neutral"), float(item.get("score") or item.get("probability") or 0.0)
    label = getattr(item, "label", None)
    score = getattr(item, "score", None)
    return str(label or "neutral"), float(score or 0.0)


def classify_image(api_token: str, model_id: str, image_bytes: bytes, timeout_s: float) -> tuple[str, float] | None:
    """Image classification via HF Inference (`image_classification` pipeline semantics)."""
    try:
        client = InferenceClient(token=api_token.strip(), timeout=timeout_s)
        ranked = client.image_classification(image_bytes, model=model_id, top_k=1)
        if not ranked:
            return None
        label, score = _scalar_label_score(ranked[0])
        return label, score
    except Exception as exc:
        logger.warning("HF Inference image_classification failed for %s: %s", model_id, exc)
        return None


def classify_text(api_token: str, model_id: str, text: str, timeout_s: float) -> tuple[str, float] | None:
    """Text classification (emotion labels) via HF Inference."""
    try:
        client = InferenceClient(token=api_token.strip(), timeout=timeout_s)
        ranked = client.text_classification(text, model=model_id, top_k=1)
        if not ranked:
            return None
        label, score = _scalar_label_score(ranked[0])
        return label, score
    except Exception as exc:
        logger.warning("HF Inference text_classification failed for %s: %s", model_id, exc)
        return None


def classify_audio(api_token: str, model_id: str, audio_bytes: bytes, timeout_s: float) -> tuple[str, float] | None:
    """Audio classification via HF Inference (`audio_classification`)."""
    try:
        client = InferenceClient(token=api_token.strip(), timeout=timeout_s)
        ranked = client.audio_classification(audio_bytes, model=model_id, top_k=1)
        if not ranked:
            return None
        label, score = _scalar_label_score(ranked[0])
        return label, score
    except Exception as exc:
        logger.warning("HF Inference audio_classification failed for %s: %s", model_id, exc)
        return None
