import json
import os
import warnings
from pathlib import Path
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
    )

    app_name: str = "Glunova FastAPI AI"
    jwt_shared_secret: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    database_url: str = "postgresql+psycopg://glunova:glunova@localhost:5432/glunova"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_vision_model: str = "llama-3.2-11b-vision-preview"
    ocr_language: str = "eng"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection_cbt: str = "cbt_knowledge"
    qdrant_collection_memory: str = "patient_memory"
    # Must match sentence-transformers/all-MiniLM-L6-v2 output (384); also used before lazy embed init.
    qdrant_vector_size: int = 384
    qdrant_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Inference API (`image_classification`); avoids local downloads when HF token + inference mode are set.
    psychology_face_emotion_model: str = "mo-thecreator/vit-Facial-Expression-Recognition"
    psychology_speech_emotion_model: str = "iic/emotion2vec_plus_large"
    # Forces local `transformers.pipeline` for text emotion when true (heavy first-time download unless cached).
    # When false but `psychology_emotion_inference_mode` is auto/inference_api and an HF token is set, text emotion uses Inference API (no weights download).
    psychology_text_emotion_use_hf: bool = False
    psychology_text_emotion_model: str = "j-hartmann/emotion-english-distilroberta-base"
    # If set, HF Inference will try this model when the primary text emotion model fails (cold start, 400, provider).
    # Set empty to disable. Use a known text-classification–friendly model (e.g. j-hartmann) as backup for multilingual hubs.
    psychology_text_emotion_hf_fallback_model: str = "j-hartmann/emotion-english-distilroberta-base"
    # HF Inference API: `auto` — try remote inference when a token is set, with local fallbacks where configured.
    # `inference_api` — remote only for modalities that use it; `local` — always on-device.
    psychology_emotion_inference_mode: str = "auto"
    # Many text-classification / audio-classification Hub models are not on HF Inference; keep false and use local pipelines.
    psychology_text_emotion_use_hf_inference: bool = False
    psychology_speech_emotion_use_hf_inference: bool = False
    psychology_hf_api_token: str = ""
    psychology_hf_inference_timeout_s: float = 8.0
    # Hugging Face InferenceClient routing: `auto` picks a Hub-registered provider (works for more models than
    # `hf-inference` alone). Set `hf-inference` only if you need the legacy proxy for a specific supported model.
    psychology_hf_inference_provider: str = "auto"
    # HF repo for speech emotion via Inference API when `psychology_speech_emotion_use_hf_inference` is true.
    psychology_speech_emotion_hf_model: str = "superb/hubert-large-superb-er"

    # Absolute path to KB assets; empty = `<repo>/psychology data` (Sanadi markdown; see `psychology/pdf_kb.py`).
    psychology_data_dir: str = ""

    # Psychology CBT KB (Qdrant): chunk versioning & hybrid rerank (bump after switching corpus / reindex).
    psychology_kb_source_version: str = "3"
    # Sanadi markdown (`sanadi_knowledge_base.md`): section split + packing (tune with eval retrieval).
    psychology_kb_sanadi_max_section_chars: int = 3400
    psychology_kb_sanadi_markdown_pack_chars: int = 920
    # Hybrid rerank: demote preamble so it steals fewer slots on concrete clinical queries (0–1).
    psychology_kb_preamble_rerank_multiplier: float = 0.82
    # Multiply score for Qdrant points with content_kind manifest_stub so Sanadi chunks win over source stubs.
    psychology_kb_manifest_stub_rerank_multiplier: float = 0.38
    # Multiply score when chunk sanadi_topic matches mental-state–preferred buckets (Phase 1 soft routing).
    psychology_kb_mental_state_topic_boost: float = 1.25
    psychology_kb_rerank_vector_weight: float = 0.75
    psychology_kb_rerank_lexical_weight: float = 0.15
    psychology_kb_rerank_category_weight: float = 0.10
    # Optional JSON file `{"vector":0.72,"lexical":0.22,"category":0.06}` overrides the three weights (eval / tuning).
    psychology_kb_rerank_config_path: str = ""
    psychology_kb_recall_limit: int = 16
    psychology_kb_final_limit_cap: int = 15
    psychology_kb_limit_min: int = 2
    psychology_kb_limit_max: int = 8
    psychology_kb_default_limit: int = 5
    # When true, Qdrant RAG skips `language` payload filters (English-only corpus; no keyword index needed).
    psychology_kb_english_only: bool = False
    # Before Qdrant memory upsert, translate patient-visible strings (FR/ar/darija/mixed sessions) via Groq.
    psychology_memory_translate_to_english: bool = True
    # Episodic retrieval (Qdrant): vector recall then decay + clinical boost rerank
    psychology_memory_recall_limit: int = 24
    psychology_memory_decay_half_life_days: float = 30.0
    psychology_memory_decay_floor: float = 0.25
    psychology_memory_clinical_boost: float = 1.45
    psychology_memory_recency_weight: float = 0.15
    psychology_memory_recency_scale_days: float = 14.0
    psychology_memory_search_limit: int = 5
    # Session-end consolidation → semantic profile + multi-chunk episodic
    psychology_consolidation_enabled: bool = True
    # When true (Postgres pool only), persist the ended session first and run consolidation + Qdrant upserts after the HTTP response (faster UX).
    psychology_consolidation_defer: bool = True
    psychology_consolidation_model: str = "llama-3.1-8b-instant"
    psychology_consolidation_max_tokens: int = 2800
    psychology_semantic_contradictions_cap: int = 12
    # Mem0 optional spike (off by default)
    mem0_enabled: bool = False

    # Sanadi voice: Groq Whisper STT (GROQ_API_KEY); synthesis is ElevenLabs only (see `_sanadi_tts_provider`).
    psychology_voice_stt_model: str = "whisper-large-v3-turbo"
    psychology_voice_max_upload_bytes: int = 10 * 1024 * 1024
    # ``none`` disables synthesis; anything else is normalized to elevenlabs.
    psychology_tts_provider: str = "elevenlabs"

    elevenlabs_api_key: str = ""
    # eleven_multilingual_v2 handles EN/FR/AR; override per language via the voice IDs below.
    psychology_elevenlabs_model: str = "eleven_multilingual_v2"
    psychology_elevenlabs_voice_en: str = "EXAVITQu4vr4xnSDxMaL"
    psychology_elevenlabs_voice_ar: str = "EXAVITQu4vr4xnSDxMaL"

    # Azure Document Intelligence (OCR)
    azure_document_intelligence_endpoint: str = ""
    azure_document_intelligence_key: str = ""

    @model_validator(mode="after")
    def _resolve_psychology_hf_token_from_env(self) -> Any:
        if (self.psychology_hf_api_token or "").strip():
            return self
        for key in ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN"):
            raw = os.getenv(key, "").strip()
            if raw:
                object.__setattr__(self, "psychology_hf_api_token", raw)
                break
        return self

    @model_validator(mode="after")
    def _sanadi_tts_provider(self) -> Any:
        """Sanadi synthesis is ElevenLabs only; ``none`` disables TTS."""
        raw = (self.psychology_tts_provider or "").strip().lower()
        if raw == "none":
            return self
        if raw != "elevenlabs":
            warnings.warn(
                f"Psychology TTS is ElevenLabs only; overriding psychology_tts_provider={raw!r} → elevenlabs.",
                stacklevel=2,
            )
            object.__setattr__(self, "psychology_tts_provider", "elevenlabs")
        return self

    @model_validator(mode="after")
    def _merge_psychology_kb_rerank_file(self) -> Any:
        path = (self.psychology_kb_rerank_config_path or "").strip()
        if not path:
            return self
        p = Path(path)
        if not p.is_file():
            warnings.warn(f"psychology_kb_rerank_config_path set but not found: {p}", stacklevel=1)
            return self
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            warnings.warn(f"Failed to read psychology rerank config {p}: {exc}", stacklevel=1)
            return self
        if not isinstance(data, dict):
            return self
        if "vector" in data:
            object.__setattr__(self, "psychology_kb_rerank_vector_weight", float(data["vector"]))
        if "lexical" in data:
            object.__setattr__(self, "psychology_kb_rerank_lexical_weight", float(data["lexical"]))
        if "category" in data:
            object.__setattr__(self, "psychology_kb_rerank_category_weight", float(data["category"]))
        return self


settings = Settings()
