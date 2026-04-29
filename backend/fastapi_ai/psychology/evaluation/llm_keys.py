"""Central helpers for evaluator API keys/models."""

from __future__ import annotations

import os


def groq_api_key() -> str:
    return (os.getenv("GROQ_API_KEY") or "").strip()


def groq_eval_model_name() -> str:
    return (os.getenv("SANADI_EVAL_GROQ_MODEL") or "llama-3.3-70b-versatile").strip()
