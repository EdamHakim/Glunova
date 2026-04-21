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
    groq_model: str = "llama-3.3-70b-versatile"
    ocr_language: str = "eng"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection_cbt: str = "cbt_knowledge"
    qdrant_collection_memory: str = "patient_memory"
    qdrant_vector_size: int = 256
    qdrant_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Absolute path to KB PDFs; empty = `<repo>/psychology data` (see `psychology/pdf_kb.py`).
    psychology_data_dir: str = ""

    # Azure Document Intelligence (OCR)
    azure_document_intelligence_endpoint: str = ""
    azure_document_intelligence_key: str = ""


settings = Settings()
