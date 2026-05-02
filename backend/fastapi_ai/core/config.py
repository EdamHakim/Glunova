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
    # Optional dedicated key used only by monitoring/services/alert_generator.
    # Falls back to groq_api_key if empty so existing modules keep working.
    groq_monitoring_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_vision_model: str = "llama-3.2-11b-vision-preview"
    ocr_language: str = "eng"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection_cbt: str = "cbt_knowledge"
    qdrant_collection_memory: str = "patient_memory"
    qdrant_vector_size: int = 256
    qdrant_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Inference API (`image_classification`); avoids local downloads when HF token + inference mode are set.
    psychology_face_emotion_model: str = "mo-thecreator/vit-Facial-Expression-Recognition"
    psychology_speech_emotion_model: str = "iic/emotion2vec_plus_large"
    # Forces local `transformers.pipeline` for text emotion when true (heavy first-time download unless cached).
    # When false but `psychology_emotion_inference_mode` is auto/inference_api and an HF token is set, text emotion uses Inference API (no weights download).
    psychology_text_emotion_use_hf: bool = False
    psychology_text_emotion_model: str = "j-hartmann/emotion-english-distilroberta-base"
    # HF Inference API: remote inference via `huggingface_hub.InferenceClient` (no local model download).
    # `auto` — use Inference API when `psychology_hf_api_token` or standard env `HF_TOKEN` / `HUGGINGFACE_HUB_TOKEN` resolves; otherwise local checkpoints.
    # `inference_api` — Inference API only (fails closed if token missing).
    # `local` — always transformers / ModelScope locally.
    psychology_emotion_inference_mode: str = "auto"
    psychology_hf_api_token: str = ""
    psychology_hf_inference_timeout_s: float = 60.0
    # Optional HF repo for speech emotion through Inference API (`audio_classification`). Empty keeps ModelScope `psychology_speech_emotion_model` for local inference.
    psychology_speech_emotion_hf_model: str = ""

    # Absolute path to KB PDFs; empty = `<repo>/psychology data` (see `psychology/pdf_kb.py`).
    psychology_data_dir: str = ""

    # Psychology CBT KB (Qdrant): chunk versioning & hybrid rerank
    psychology_kb_source_version: str = "1"
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
