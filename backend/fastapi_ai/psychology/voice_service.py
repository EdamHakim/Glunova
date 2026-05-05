"""Sanadi voice STT (Groq Whisper) and TTS (ElevenLabs / Groq Orpheus)."""

from __future__ import annotations

import io
import logging
from typing import Literal

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

LanguageLiterals = Literal["en", "fr", "ar", "darija", "mixed"]

GROQ_SPEECH_URL = "https://api.groq.com/openai/v1/audio/speech"


class VoiceConfigurationError(RuntimeError):
    """Missing API credentials or disabled provider."""

    pass


class GroqSpeechError(RuntimeError):
    """Groq `/audio/speech` returned an error (e.g. model terms not accepted)."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ElevenLabsSpeechError(RuntimeError):
    """ElevenLabs TTS returned an error."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _groq_speech_error_from_response(response: httpx.Response) -> GroqSpeechError:
    """Map Groq JSON error body to a client-facing exception."""
    detail = f"Groq speech HTTP error: {response.status_code}"
    client_status = 502
    try:
        data = response.json()
        err = data.get("error") or {}
        groq_msg = (err.get("message") or "").strip()
        code = err.get("code")
        if groq_msg:
            detail = groq_msg
        if code == "model_terms_required":
            # Org admin must accept model terms in Groq Console; not fixable from this API.
            client_status = 503
    except Exception:
        pass
    return GroqSpeechError(detail, status_code=client_status)


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


def _groq_tts_model_and_voice(language: LanguageLiterals) -> tuple[str, str]:
    """Return (model_id, voice_id) for Groq `audio/speech`."""
    if language in ("ar", "darija"):
        model = (settings.psychology_groq_tts_model_ar or "canopylabs/orpheus-arabic-saudi").strip()
        voice = (settings.psychology_groq_tts_voice_ar or "noura").strip()
        return model, voice
    # en, fr, mixed — Orpheus English (no dedicated FR model; French text is read with English voice).
    model = (settings.psychology_groq_tts_model_en or "canopylabs/orpheus-v1-english").strip()
    voice = (settings.psychology_groq_tts_voice_en or "hannah").strip()
    return model, voice


ELEVENLABS_TTS_TIMESTAMPS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"


def _elevenlabs_voice_id(language: LanguageLiterals) -> str:
    if language in ("ar", "darija"):
        return (settings.psychology_elevenlabs_voice_ar or "EXAVITQu4vr4xnSDxMaL").strip()
    return (settings.psychology_elevenlabs_voice_en or "EXAVITQu4vr4xnSDxMaL").strip()


def _chars_to_word_timestamps(
    chars: list[str],
    char_starts: list[float],
    char_ends: list[float],
) -> tuple[list[str], list[float], list[float]]:
    """Convert ElevenLabs character-level alignment to word-level timestamps in milliseconds."""
    words: list[str] = []
    wtimes: list[float] = []
    wdurations: list[float] = []
    current = ""
    word_start: float | None = None
    word_end: float = 0.0
    for i, ch in enumerate(chars):
        if ch in (" ", "\n", "\t"):
            if current:
                words.append(current)
                wtimes.append((word_start or 0.0) * 1000.0)
                wdurations.append((word_end - (word_start or 0.0)) * 1000.0)
                current = ""
                word_start = None
        else:
            if word_start is None:
                word_start = char_starts[i] if i < len(char_starts) else 0.0
            word_end = char_ends[i] if i < len(char_ends) else 0.0
            current += ch
    if current:
        words.append(current)
        wtimes.append((word_start or 0.0) * 1000.0)
        wdurations.append((word_end - (word_start or 0.0)) * 1000.0)
    return words, wtimes, wdurations


def _synthesize_elevenlabs(text: str, *, language: LanguageLiterals) -> tuple[bytes, str]:
    """Synthesize via ElevenLabs /with-timestamps.

    Returns JSON bytes (content-type application/json) containing:
      audio_b64   — base64 MP3
      content_type — "audio/mpeg"
      words       — word strings
      wtimes      — word start times in ms (from normalizedAlignment)
      wdurations  — word durations in ms
    """
    import base64
    import json as _json

    api_key = (settings.elevenlabs_api_key or "").strip()
    if not api_key:
        raise VoiceConfigurationError("ELEVENLABS_API_KEY not configured")

    trimmed = text.strip()
    if not trimmed:
        raise ValueError("text is empty")

    voice_id = _elevenlabs_voice_id(language)
    model_id = (settings.psychology_elevenlabs_model or "eleven_multilingual_v2").strip()
    url = ELEVENLABS_TTS_TIMESTAMPS_URL.format(voice_id=voice_id)
    payload = {
        "text": trimmed,
        "model_id": model_id,
        "output_format": "mp3_44100_128",
    }
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    logger.debug("tts elevenlabs lang=%s voice=%s model=%s", language, voice_id, model_id)
    timeout = httpx.Timeout(60.0, connect=15.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=payload, headers=headers)
            if r.status_code >= 400:
                logger.warning("ElevenLabs TTS failed (%s): %s", r.status_code, r.text[:500])
                detail = f"ElevenLabs TTS error {r.status_code}"
                try:
                    body = r.json()
                    msg = (body.get("detail") or {})
                    if isinstance(msg, dict):
                        msg = msg.get("message") or ""
                    if msg:
                        detail = str(msg)
                except Exception:
                    pass
                raise ElevenLabsSpeechError(detail, status_code=502)

            data = r.json()
    except ElevenLabsSpeechError:
        raise
    except httpx.HTTPError as exc:
        raise ElevenLabsSpeechError(f"ElevenLabs TTS request failed: {exc}", status_code=502) from exc

    audio_b64: str = data.get("audio_base64") or ""
    alignment = data.get("normalized_alignment") or data.get("alignment") or {}
    chars: list[str] = alignment.get("characters") or []
    char_starts: list[float] = alignment.get("character_start_times_seconds") or []
    char_ends: list[float] = alignment.get("character_end_times_seconds") or []
    words, wtimes, wdurations = _chars_to_word_timestamps(chars, char_starts, char_ends)

    result = _json.dumps({
        "audio_b64": audio_b64,
        "content_type": "audio/mpeg",
        "words": words,
        "wtimes": wtimes,
        "wdurations": wdurations,
    })
    return result.encode(), "application/json"


def synthesize_speech_mp3(text: str, *, language: LanguageLiterals) -> tuple[bytes, str]:
    """
    Synthesize speech for Sanadi replies. Routes to ElevenLabs or Groq based on
    ``PSYCHOLOGY_TTS_PROVIDER`` (elevenlabs | groq | none).

    Returns:
        (audio_bytes, content_type)

    Raises:
        VoiceConfigurationError: Provider disabled or missing API key.
        ElevenLabsSpeechError / GroqSpeechError: Upstream error.
    """
    provider = (settings.psychology_tts_provider or "groq").strip().lower()

    if provider == "none":
        raise VoiceConfigurationError("Psychology TTS provider is disabled (psychology_tts_provider=none)")

    if provider == "elevenlabs":
        return _synthesize_elevenlabs(text, language=language)

    # groq (default)
    api_key = (settings.groq_api_key or "").strip().strip("'\"")
    if not api_key:
        raise VoiceConfigurationError("GROQ_API_KEY not configured (required for Groq TTS)")

    trimmed = text.strip()
    if not trimmed:
        raise ValueError("text is empty")

    # Groq Orpheus: max 200 characters per request; only WAV is supported.
    clipped = trimmed[:200]
    if len(trimmed) > 200:
        logger.debug("tts groq: truncating input from %s to 200 chars (Orpheus limit)", len(trimmed))

    model, voice = _groq_tts_model_and_voice(language)
    payload = {
        "model": model,
        "input": clipped,
        "voice": voice,
        "response_format": "wav",
    }

    logger.debug("tts groq lang=%s model=%s voice=%s", language, model, voice)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(120.0, connect=30.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(GROQ_SPEECH_URL, json=payload, headers=headers)
            if r.status_code >= 400:
                logger.warning("Groq speech failed (%s): %s", r.status_code, r.text[:500])
                raise _groq_speech_error_from_response(r)
            body = r.content
    except GroqSpeechError:
        raise
    except httpx.HTTPError as exc:
        raise GroqSpeechError(f"Groq speech request failed: {exc}", status_code=502) from exc

    return body, "audio/wav"


def is_groq_configured() -> bool:
    return bool((settings.groq_api_key or "").strip())


def is_tts_configured() -> bool:
    provider = (settings.psychology_tts_provider or "groq").strip().lower()
    if provider == "none":
        return False
    if provider == "elevenlabs":
        return bool((settings.elevenlabs_api_key or "").strip())
    return bool((settings.groq_api_key or "").strip())
