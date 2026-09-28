import os
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "BIS Compliance Assistant"
    API_V1_STR: str = ""
    VERSION: str = "3.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Auth
    API_KEY: str = os.getenv("API_KEY", "demo-key-123")

    # Bhashini translation
    BHASHINI_USER_ID: str = os.getenv("BHASHINI_USER_ID", "")
    BHASHINI_API_KEY: str = os.getenv("BHASHINI_API_KEY", "")
    BHASHINI_PIPELINE_ID: str = os.getenv("BHASHINI_PIPELINE_ID", "64392f96daac500b55c543cd")
    BHASHINI_PIPELINE_URL: str = os.getenv(
        "BHASHINI_PIPELINE_URL",
        "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline",
    )

    # LLM providers
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")  # gemini | ollama | mock
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))

    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

    # OCR
    OCR_PROVIDER: str = os.getenv("OCR_PROVIDER", "mock")  # tesseract | paddleocr | mock
    TESSERACT_CMD: str = os.getenv("TESSERACT_CMD", "tesseract")

    # Document storage
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))
    ALLOWED_MIME_TYPES: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/tiff",
        "image/webp",
    ]

    # Vector store (FAISS) — path to pre-built index from MAIN backend
    VECTORSTORE_PATH: str = os.getenv(
        "VECTORSTORE_PATH",
        r"C:\Users\Admin pc\Desktop\BIS-Sahayta-main\BIS-RAG-master\storage\vectorstore",
    )
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))

    # Chat session DB
    SESSION_DB_PATH: str = os.getenv("SESSION_DB_PATH", "sessions.db")


settings = Settings()

