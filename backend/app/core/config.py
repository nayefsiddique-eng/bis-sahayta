import os
from pathlib import Path
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

# Absolute path to backend directory (where config.py lives under app/core)
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    PROJECT_NAME: str = "BIS Compliance Assistant"
    API_V1_STR: str = ""
    VERSION: str = "3.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Auth
    API_KEY: str = "demo-key-123"

    # Bhashini translation
    BHASHINI_USER_ID: str = ""
    BHASHINI_API_KEY: str = ""
    BHASHINI_PIPELINE_ID: str = "64392f96daac500b55c543cd"
    BHASHINI_PIPELINE_URL: str = (
        "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
    )

    # LLM providers
    LLM_PROVIDER: str = "mock"  # gemini | ollama | mock
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    # Multi-model LLM routing (Gemma 4 + Qwen fallback)
    LLM_DEFAULT_MODEL: str = "gemini"          # auto | gemini | gemma4 | qwen
    LLM_FALLBACK_ORDER: str = "gemma4,qwen"    # comma-separated fallback chain
    LLM_REQUEST_TIMEOUT_SECONDS: int = 30      # local model HTTP timeout
    LLM_LOCAL_MAX_CONCURRENCY: int = 2         # GPU semaphore (local models only)
    LLM_COOLDOWN_SECONDS: int = 60             # skip Gemini after 429 for N seconds
    GEMMA4_BASE_URL: str = "http://localhost:11434/v1"  # OpenAI-compatible endpoint
    GEMMA4_MODEL_NAME: str = "gemma3:4b"
    GEMMA4_API_KEY: str = ""                   # leave blank for unauthenticated local
    QWEN_BASE_URL: str = "http://localhost:11434/v1"
    QWEN_MODEL_NAME: str = "qwen2.5:7b"
    QWEN_API_KEY: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 300

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # OCR
    OCR_PROVIDER: str = "mock"  # tesseract | paddleocr | mock
    TESSERACT_CMD: str = "tesseract"

    # Document storage
    UPLOAD_DIR: str = str(BACKEND_DIR / "uploads")
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_MIME_TYPES: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/tiff",
        "image/webp",
    ]

    # Vector store (FAISS) — default to backend/storage/vectorstore relative to config.py
    VECTORSTORE_PATH: str = str(BACKEND_DIR / "storage" / "vectorstore")
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    RAG_TOP_K: int = 5
    RAG_MIN_SCORE: float = 0.30

    # Chat session DB
    SESSION_DB_PATH: str = str(BACKEND_DIR / "sessions.db")


settings = Settings()
