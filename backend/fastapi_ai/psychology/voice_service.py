"""Sanadi voice STT (Groq Whisper) and TTS (OpenAI Speech) proxied via FastAPI."""

from __future__ import annotations

import io
import logging
from typing import Literal

from core.config import settings

logger = logging.getLogger(__name__)

LanguageLiterals = Literal["en", "fr", "ar", "darija", "mixed"]


class VoiceConfigurationError(RuntimeError):
    """Missing API credentials or disabled provider."""

    pass


def _groq_whisper_language(hint: str | None) -> str | None:
    if not hint or not hint.strip():
        return None
    raw = hint.strip().lower()
    if raw == "darija":
        return "ar"
    if raw == "mixed":
        return None
    if raw in {"en", "fr", "ar"}:
        return raw
    return None


def transcribe_audio_bytes(
    data: bytes,
    *,
    filename: str,
    language_hint: str | None = None,
) -> tuple[str, str | None]:
    """
    Return (transcript, language_echo). Whisper language is hinted when possible (darija→ar).

    Raises:
        VoiceConfigurationError: Missing Groq API key.
        ValueError: Empty audio or oversized payload handled by caller.
    """
    api_key = (settings.groq_api_key or "").strip().strip("'\"")
    if not api_key:
        raise VoiceConfigurationError("GROQ_API_KEY not configured")

    lang = _groq_whisper_language(language_hint)

    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError("groq package is required for voice transcription") from exc

    client = Groq(api_key=api_key)
    fname = filename.lower()
    if fname.endswith(".webm"):
        mime_guess = "audio/webm"
    elif fname.endswith(".wav"):
        mime_guess = "audio/wav"
    elif fname.endswith((".mpeg", ".mp3", ".mpga")):
        mime_guess = "audio/mpeg"
    elif fname.endswith(".ogg") or fname.endswith(".oga"):
        mime_guess = "audio/ogg"
    else:
        mime_guess = "application/octet-stream"
    buffered = io.BytesIO(data)
    buffered.seek(0)

    kwargs: dict[str, object] = {
        "model": settings.psychology_voice_stt_model,
        "file": (filename, buffered, mime_guess),
        "temperature": 0,
    }
    if lang:
        kwargs["language"] = lang

    transcription = client.audio.transcriptions.create(**kwargs)
    text = (transcription.text or "").strip()
    guessed = lang or (language_hint.strip().lower() if language_hint and language_hint.strip() else None)
    return text, guessed


def synthesize_speech_mp3(text: str, *, language: LanguageLiterals) -> tuple[bytes, str]:
    """
    Generate MP3 speech bytes via OpenAI Audio Speech API.

    Returns:
        (mp3_bytes, content_type audio/mpeg).

    Raises:
        VoiceConfigurationError: Provider none or OPENAI_API_KEY missing.
        RuntimeError: OpenAI HTTP or transport failure.
    """
    if (settings.psychology_tts_provider or "").strip().lower() == "none":
        raise VoiceConfigurationError("Psychology TTS provider is disabled (psychology_tts_provider=none)")

    api_key = (settings.openai_api_key or "").strip().strip("'\"")
    if not api_key:
        raise VoiceConfigurationError("OPENAI_API_KEY not configured")

    trimmed = text.strip()
    if not trimmed:
        raise ValueError("text is empty")

    import httpx

    logger.debug("tts openai lang=%s model=%s", language, settings.psychology_openai_tts_model)

    payload = {
        "model": settings.psychology_openai_tts_model,
        "input": trimmed[:4000],
        "voice": settings.psychology_openai_tts_voice,
        "response_format": "mp3",
    }

    url = "https://api.openai.com/v1/audio/speech"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(120.0, connect=30.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=payload, headers=headers)
            if r.status_code >= 400:
                logger.warning("OpenAI speech failed (%s): %s", r.status_code, r.text[:200])
            r.raise_for_status()
            return r.content, "audio/mpeg"
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"OpenAI speech HTTP error: {exc.response.status_code}") from exc


def is_groq_configured() -> bool:
    return bool((settings.groq_api_key or "").strip())


def is_tts_configured() -> bool:
    if (settings.psychology_tts_provider or "").strip().lower() == "none":
        return False
    return bool((settings.openai_api_key or "").strip())
