from pathlib import Path
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
    # Lighter default (~86M params) to avoid multi-GB Hub downloads on dev machines.
    # For the previous ViT checkpoint, set PSYCHOLOGY_FACE_EMOTION_MODEL=trpakov/vit-face-expression
    psychology_face_emotion_model: str = "dima806/facial_emotions_image_detection"
    psychology_speech_emotion_model: str = "iic/emotion2vec_plus_large"
    # Huge multilingual checkpoint (~GB+ download) — blocks /psychology/message on first send if enabled.
    # Default: off — use keyword heuristics in _text_emotion instead (instant, no HF).
    # Enable with PSYCHOLOGY_TEXT_EMOTION_USE_HF=true; optionally set psychology_text_emotion_model to:
    #   tabularisai/multilingual-emotion-classification  (heavy, multilingual)
    #   j-hartmann/emotion-english-distilroberta-base   (much lighter English)
    psychology_text_emotion_use_hf: bool = False
    psychology_text_emotion_model: str = "j-hartmann/emotion-english-distilroberta-base"
    # Absolute path to KB PDFs; empty = `<repo>/psychology data` (see `psychology/pdf_kb.py`).
    psychology_data_dir: str = ""

    # Azure Document Intelligence (OCR)
    azure_document_intelligence_endpoint: str = ""
    azure_document_intelligence_key: str = ""


settings = Settings()
