import asyncio

import pytest
from fastapi import HTTPException


def _make_provider(message):
    from app.services.llm_service import GeminiProvider

    calls = {"n": 0}

    class FakeModel:
        def generate_content(self, *args, **kwargs):
            calls["n"] += 1
            raise Exception(message)

    provider = GeminiProvider.__new__(GeminiProvider)
    provider._model = FakeModel()
    return provider, calls


@pytest.mark.asyncio
async def test_gemini_daily_quota_is_not_retried_and_reports_quota_id():
    provider, calls = _make_provider(
        '429 You exceeded your current quota. quota_id: "GenerateRequestsPerDayPerProjectPerModel-FreeTier" Please retry in 3s.'
    )
    with pytest.raises(HTTPException) as info:
        await provider.complete("hello")
    assert info.value.status_code == 429
    assert calls["n"] == 1
    assert info.value.detail["quota_id"] == "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
    assert info.value.detail["retry_after_seconds"] == 4


@pytest.mark.asyncio
async def test_gemini_per_minute_quota_retries_then_reports_429(monkeypatch):
    provider, calls = _make_provider(
        '429 You exceeded your current quota. quota_id: "GenerateRequestsPerMinutePerProjectPerModel-FreeTier" Please retry in 1s.'
    )
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    with pytest.raises(HTTPException) as info:
        await provider.complete("hello")
    assert info.value.status_code == 429
    assert calls["n"] == 3
    assert [s for s in slept if s] == [2, 2]
    assert info.value.detail["quota_id"] == "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"