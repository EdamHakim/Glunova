from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
import shlex
import subprocess
from uuid import uuid4
from urllib.parse import unquote, urlparse

from django.conf import settings
import httpx

from .models import KidsProfile


class VoiceCloneConfigurationError(RuntimeError):
    pass


class VoiceCloneProviderError(RuntimeError):
    pass


def _api_key() -> str:
    return os.getenv("ELEVENLABS_API_KEY", "").strip().strip("'\"")


def _voice_model() -> str:
    return os.getenv("KIDS_ELEVENLABS_TTS_MODEL", "eleven_multilingual_v2").strip() or "eleven_multilingual_v2"


def _provider() -> str:
    """Kids parent voice backend: pocket (local Kyutai), fish, or elevenlabs.

    Explicit values:
    - pocket | pocket-tts | kyutai | local | offline → Pocket TTS (CPU / local CLI)
    - fish → Fish Audio API
    - elevenlabs | 11labs | eleven → ElevenLabs API

    If KIDS_VOICE_CLONE_PROVIDER is unset or blank: use Fish when configured, else ElevenLabs
    when configured, else Pocket (works offline with pocket-tts + optional FFmpeg).
    """
    raw = (os.getenv("KIDS_VOICE_CLONE_PROVIDER") or "").strip().lower()
    pocket_aliases = {"pocket", "pocket-tts", "kyutai", "local", "offline"}
    if raw in pocket_aliases:
        return "pocket"
    if raw == "fish":
        return "fish"
    if raw in {"elevenlabs", "11labs", "eleven"}:
        return "elevenlabs"
    if not raw:
        if _fish_api_key():
            return "fish"
        if _api_key():
            return "elevenlabs"
        return "pocket"
    # Unknown explicit label: keep legacy behavior (mostly ElevenLabs path)
    return "elevenlabs"


def _pocket_tts_command() -> list[str]:
    """Resolve the Pocket TTS CLI.

    On Windows, `pip install pocket-tts` exposes `python -m pocket_tts`, not always `pocket-tts` on PATH.
    Set KIDS_POCKET_TTS_COMMAND to override (e.g. ``uvx pocket-tts``).
    """
    configured = (os.getenv("KIDS_POCKET_TTS_COMMAND") or "").strip()
    if configured:
        return shlex.split(configured, posix=False)
    if shutil.which("pocket-tts"):
        return ["pocket-tts"]
    return [sys.executable, "-m", "pocket_tts"]


def _pocket_tts_language() -> str:
    return os.getenv("KIDS_POCKET_TTS_LANGUAGE", "english").strip() or "english"


def _pocket_tts_timeout_s() -> int:
    try:
        return max(30, int(os.getenv("KIDS_POCKET_TTS_TIMEOUT_S", "240")))
    except ValueError:
        return 240


def _pocket_subprocess_env() -> dict[str, str]:
    """Ensure Hugging Face token is visible to `python -m pocket_tts` (gated voice-clone weights)."""
    env = dict(os.environ)
    token = (
        env.get("HF_TOKEN", "").strip()
        or env.get("HUGGINGFACE_HUB_TOKEN", "").strip()
        or env.get("HUGGINGFACE_API_KEY", "").strip()
    )
    if token:
        env["HF_TOKEN"] = token
        env["HUGGINGFACE_HUB_TOKEN"] = token
    return env


def _fish_api_key() -> str:
    return (
        os.getenv("FISH_AUDIO_API_KEY", "")
        or os.getenv("FISH_API_KEY", "")
        or os.getenv("FISHAUDIO_API_KEY", "")
    ).strip().strip("'\"")


def _fish_tts_model() -> str:
    configured = os.getenv("KIDS_FISH_TTS_MODEL", "s2-pro").strip()
    return configured if configured in {"s1", "s2-pro"} else "s2-pro"


def _local_media_path_from_url(media_url: str) -> Path:
    parsed_path = unquote(urlparse(media_url or "").path)
    if not parsed_path.startswith(settings.MEDIA_URL):
        raise VoiceCloneConfigurationError("Parent voice sample is not stored in local media.")
    relative_path = parsed_path.removeprefix(settings.MEDIA_URL).lstrip("/")
    media_root = settings.MEDIA_ROOT.resolve()
    candidate = (media_root / relative_path).resolve()
    if not str(candidate).startswith(str(media_root)) or not candidate.exists():
        raise VoiceCloneConfigurationError("Parent voice sample file is missing.")
    return candidate


def _sample_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".wav":
        return "audio/wav"
    if suffix == ".mp3":
        return "audio/mpeg"
    if suffix == ".m4a":
        return "audio/mp4"
    if suffix == ".ogg":
        return "audio/ogg"
    if suffix == ".webm":
        return "audio/webm"
    return "application/octet-stream"


def _pocket_voice_reference_audio(sample_path: Path) -> tuple[Path, Path | None]:
    """Return (--voice path, temp file path to delete after use, if any).

    Pocket TTS accepts wav/mp3/flac/ogg directly. Browser uploads are often WebM/M4A;
    we convert those with FFmpeg when available.
    """
    suf = sample_path.suffix.lower()
    if suf in {".wav", ".mp3", ".flac", ".ogg"}:
        return sample_path, None
    if suf in {".webm", ".m4a", ".mp4"}:
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        out = Path(tmp)
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(sample_path),
                    "-ar",
                    "44100",
                    "-ac",
                    "1",
                    str(out),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except FileNotFoundError as exc:
            out.unlink(missing_ok=True)
            raise VoiceCloneConfigurationError(
                "Local voice (Pocket TTS) needs FFmpeg to convert WebM/M4A recordings. "
                "Install FFmpeg, or upload a WAV/MP3 sample."
            ) from exc
        except subprocess.CalledProcessError as exc:
            out.unlink(missing_ok=True)
            detail = (exc.stderr or b"").decode(errors="replace").strip()[:240]
            raise VoiceCloneProviderError(f"FFmpeg could not convert the parent voice sample: {detail}") from exc
        return out, out
    raise VoiceCloneConfigurationError(
        "Kyutai Pocket TTS needs WAV/MP3/FLAC/OGG, or WebM/M4A with FFmpeg installed."
    )


def synthesize_with_pocket_parent_voice(profile: KidsProfile, text: str) -> tuple[bytes, str, str]:
    trimmed = " ".join((text or "").split())
    if not trimmed:
        raise ValueError("Text is empty.")
    if not profile.parent_voice_sample_url:
        raise VoiceCloneConfigurationError("No parent voice sample has been recorded yet.")

    sample_path = _local_media_path_from_url(profile.parent_voice_sample_url)
    voice_ref, temp_converted = _pocket_voice_reference_audio(sample_path)

    out_dir = settings.MEDIA_ROOT / "kids" / "generated-voices"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"{uuid4().hex}.wav"
    command = [
        *_pocket_tts_command(),
        "generate",
        "--text",
        trimmed[:1200],
        "--voice",
        str(voice_ref),
        "--output-path",
        str(output_path),
        "--language",
        _pocket_tts_language(),
        "--quiet",
    ]
    try:
        try:
            completed = subprocess.run(
                command,
                cwd=str(settings.BASE_DIR),
                capture_output=True,
                text=True,
                timeout=_pocket_tts_timeout_s(),
                check=False,
                env=_pocket_subprocess_env(),
            )
        except FileNotFoundError as exc:
            raise VoiceCloneConfigurationError(
                "Pocket TTS is not installed. Use cloud voice instead: set KIDS_VOICE_CLONE_PROVIDER=fish "
                "and FISH_AUDIO_API_KEY, or elevenlabs and ELEVENLABS_API_KEY. "
                "Optional local setup: pip install -r requirements-kids-pocket-tts.txt"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise VoiceCloneProviderError("Kyutai Pocket TTS timed out while generating speech.") from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "unknown error").strip()
            low = detail.lower()
            if "voice cloning" in low or "could not download the weights" in low:
                raise VoiceCloneProviderError(
                    f"Kyutai voice-clone weights are gated. Accept the model at "
                    f"https://huggingface.co/kyutai/pocket-tts (use the same HF account as your token), "
                    f"and set HF_TOKEN or HUGGINGFACE_API_KEY. Raw error: {detail[:200]}"
                )
            raise VoiceCloneProviderError(f"Kyutai Pocket TTS failed: {detail[:240]}")
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise VoiceCloneProviderError("Kyutai Pocket TTS did not produce an audio file.")

        profile.parent_voice_profile_id = f"pocket:{sample_path.name}"
        profile.save(update_fields=["parent_voice_profile_id", "updated_at"])
        return output_path.read_bytes(), "audio/wav", f"pocket:{sample_path.name}"
    finally:
        if temp_converted is not None:
            temp_converted.unlink(missing_ok=True)


def ensure_fish_parent_voice_clone(profile: KidsProfile) -> str:
    api_key = _fish_api_key()
    if not api_key:
        raise VoiceCloneConfigurationError("FISH_AUDIO_API_KEY is not configured.")
    if profile.parent_voice_profile_id.startswith("fish:"):
        return profile.parent_voice_profile_id.removeprefix("fish:")
    if (
        profile.parent_voice_profile_id
        and not profile.parent_voice_profile_id.startswith("local-parent-voice-")
        and not profile.parent_voice_profile_id.startswith("elevenlabs:")
    ):
        return profile.parent_voice_profile_id
    if not profile.parent_voice_sample_url:
        raise VoiceCloneConfigurationError("No parent voice sample has been recorded yet.")

    sample_path = _local_media_path_from_url(profile.parent_voice_sample_url)
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "title": f"Glunova parent voice {profile.patient_id}",
        "description": "Parent voice clone for the Glunova kids assistant.",
        "visibility": "private",
        "type": "tts",
        "train_mode": "fast",
        "enhance_audio_quality": "true",
    }
    with sample_path.open("rb") as sample_file:
        files = [("voices", (sample_path.name, sample_file, _sample_content_type(sample_path)))]
        with httpx.Client(timeout=120.0) as client:
            response = client.post("https://api.fish.audio/model", headers=headers, data=data, files=files)
    if response.status_code >= 400:
        raise VoiceCloneProviderError(f"Fish voice clone creation failed: {response.text[:240]}")
    payload = response.json()
    voice_id = str(payload.get("_id") or payload.get("id") or "").strip()
    if not voice_id:
        raise VoiceCloneProviderError("Fish voice clone creation returned no model id.")

    profile.parent_voice_profile_id = f"fish:{voice_id}"
    profile.save(update_fields=["parent_voice_profile_id", "updated_at"])
    return voice_id


def synthesize_with_fish_parent_voice(profile: KidsProfile, text: str) -> tuple[bytes, str, str]:
    trimmed = " ".join((text or "").split())
    if not trimmed:
        raise ValueError("Text is empty.")
    api_key = _fish_api_key()
    if not api_key:
        raise VoiceCloneConfigurationError("FISH_AUDIO_API_KEY is not configured.")
    voice_id = ensure_fish_parent_voice_clone(profile)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "model": _fish_tts_model(),
    }
    payload = {
        "text": trimmed[:1200],
        "reference_id": voice_id,
        "format": "mp3",
        "mp3_bitrate": 128,
        "latency": "balanced",
        "normalize": True,
        "temperature": 0.7,
        "top_p": 0.7,
        "prosody": {
            "speed": 1,
            "volume": 0,
            "normalize_loudness": True,
        },
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post("https://api.fish.audio/v1/tts", headers=headers, json=payload)
    if response.status_code >= 400:
        raise VoiceCloneProviderError(f"Fish voice synthesis failed: {response.text[:240]}")
    return response.content, response.headers.get("content-type", "audio/mpeg"), f"fish:{voice_id}"


def _pocket_cloud_fallback_enabled() -> bool:
    return os.getenv("KIDS_VOICE_CLOUD_FALLBACK", "false").strip().lower() in {"1", "true", "yes"}


def synthesize_with_elevenlabs_parent_voice(profile: KidsProfile, text: str) -> tuple[bytes, str, str]:
    trimmed = " ".join((text or "").split())
    if not trimmed:
        raise ValueError("Text is empty.")
    if not _api_key():
        raise VoiceCloneConfigurationError("ELEVENLABS_API_KEY is not configured.")
    voice_id = ensure_parent_voice_clone(profile)
    headers = {
        "xi-api-key": _api_key(),
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }
    payload = {
        "text": trimmed[:1200],
        "model_id": _voice_model(),
        "voice_settings": {
            "stability": 0.55,
            "similarity_boost": 0.85,
            "style": 0.2,
            "use_speaker_boost": True,
        },
    }
    with httpx.Client(timeout=90.0) as client:
        response = client.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}", headers=headers, json=payload)
    if response.status_code >= 400:
        raise VoiceCloneProviderError(f"Voice synthesis failed: {response.text[:240]}")
    return response.content, response.headers.get("content-type", "audio/mpeg"), voice_id


def ensure_parent_voice_clone(profile: KidsProfile) -> str:
    api_key = _api_key()
    if not api_key:
        raise VoiceCloneConfigurationError("ELEVENLABS_API_KEY is not configured.")
    if profile.parent_voice_profile_id and not profile.parent_voice_profile_id.startswith("local-parent-voice-"):
        return profile.parent_voice_profile_id.removeprefix("elevenlabs:")
    if not profile.parent_voice_sample_url:
        raise VoiceCloneConfigurationError("No parent voice sample has been recorded yet.")

    sample_path = _local_media_path_from_url(profile.parent_voice_sample_url)
    headers = {"xi-api-key": api_key}
    data = {
        "name": f"Glunova parent voice {profile.patient_id}",
        "description": "Parent voice clone for the Glunova kids assistant.",
    }
    with sample_path.open("rb") as sample_file:
        files = {"files": (sample_path.name, sample_file, "audio/webm")}
        with httpx.Client(timeout=90.0) as client:
            response = client.post("https://api.elevenlabs.io/v1/voices/add", headers=headers, data=data, files=files)
    if response.status_code >= 400:
        raise VoiceCloneProviderError(f"Voice clone creation failed: {response.text[:240]}")
    voice_id = str(response.json().get("voice_id", "")).strip()
    if not voice_id:
        raise VoiceCloneProviderError("Voice clone creation returned no voice_id.")

    profile.parent_voice_profile_id = f"elevenlabs:{voice_id}"
    profile.save(update_fields=["parent_voice_profile_id", "updated_at"])
    return voice_id


def synthesize_with_parent_voice(profile: KidsProfile, text: str) -> tuple[bytes, str, str]:
    backend = _provider()
    if backend == "pocket":
        try:
            return synthesize_with_pocket_parent_voice(profile, text)
        except (VoiceCloneConfigurationError, VoiceCloneProviderError) as pocket_err:
            if not _pocket_cloud_fallback_enabled():
                raise
            if _fish_api_key():
                try:
                    return synthesize_with_fish_parent_voice(profile, text)
                except (VoiceCloneConfigurationError, VoiceCloneProviderError):
                    pass
            if _api_key():
                return synthesize_with_elevenlabs_parent_voice(profile, text)
            raise pocket_err
    if backend == "fish":
        return synthesize_with_fish_parent_voice(profile, text)

    return synthesize_with_elevenlabs_parent_voice(profile, text)
