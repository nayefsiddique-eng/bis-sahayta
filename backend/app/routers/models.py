"""
GET /models — returns availability status of configured LLM models.
Frontend uses this to build the model selector and disable unavailable options.
"""
from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter

from app.services.llm_service import get_llm_router

router = APIRouter(prefix="/models", tags=["models"])

# Simple in-process cache: (timestamp, payload)
_cache: tuple[float, list[dict]] = (0.0, [])
_CACHE_TTL = 10.0  # seconds


@router.get("", summary="List LLM model availability")
def list_models() -> dict:
    """
    Returns the list of configured LLM models and their availability status.

    Availability is a cached snapshot (TTL 10 s) — no live network ping is made,
    so this endpoint always responds instantly.

    Response shape:
    ```json
    {
      "models": [
        {"key": "gemini",  "label": "Gemini (Google)", "available": true,  "reason": null},
        {"key": "gemma4",  "label": "Gemma 4",         "available": false, "reason": "Not configured ..."},
        {"key": "qwen",    "label": "Qwen",             "available": false, "reason": "Not configured ..."}
      ],
      "default": "gemini"
    }
    ```
    """
    global _cache
    now = time.monotonic()
    if now - _cache[0] < _CACHE_TTL and _cache[1]:
        models = _cache[1]
    else:
        models = get_llm_router().model_status()
        _cache = (now, models)

    from app.core.config import settings
    return {"models": models, "default": settings.LLM_DEFAULT_MODEL}
