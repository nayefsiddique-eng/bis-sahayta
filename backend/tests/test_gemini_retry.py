import asyncio

import pytest
from fastapi import HTTPException

from app.services.llm_service import GeminiProvider


class _Boom:
    def generate_content(self, *a, **k):
        raise Exception("429 Resource exhausted. Please retry in 40s")


def test_gemini_429_maps_to_http_429_with_retry_after():
    prov = GeminiProvider.__new__(GeminiProvider)
    prov._model = _Boom()
    with pytest.raises(HTTPException) as ei:
        asyncio.run(prov.complete("hi"))
    assert ei.value.status_code == 429
    assert ei.value.headers["Retry-After"] == "41"
