"""Central helpers for evaluator API keys (OpenAI vs Google Gemini AI Studio)."""

from __future__ import annotations

import os


def openai_api_key() -> str:
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def google_api_key() -> str:
    """Google AI Studio / Gemini key (`GOOGLE_API_KEY` or `GEMINI_API_KEY`)."""
    return (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()


def gemini_eval_model_name() -> str:
    return (os.getenv("SANADI_EVAL_GEMINI_MODEL") or "gemini-2.0-flash").strip()
