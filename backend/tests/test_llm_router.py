"""
Tests for LLMRouter — circuit breaker, fallback chain, explicit model selection,
<think> tag stripping, concurrency semaphore. All mocked — no real API keys or GPU.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.services.llm_service as llm_mod
from app.services.llm_service import (
    LLMRouter,
    LocalOpenAIProvider,
    _strip_think_tags,
    get_llm_router,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_router(gemini_provider=None, local_cfg: dict | None = None) -> LLMRouter:
    """Return a fresh LLMRouter with injected mock providers."""
    router = LLMRouter.__new__(LLMRouter)
    router._gemini_cooldown_until = 0.0
    router._sem = asyncio.Semaphore(2)

    if gemini_provider is None:
        mock_p = AsyncMock()
        mock_p.name = "mock"
        mock_p.complete = AsyncMock(return_value="mock answer")
        gemini_provider = mock_p

    # Patch get_llm_provider so _call_gemini uses our mock
    router._mock_provider = gemini_provider

    local_cfg = local_cfg or {}
    router._local = {}
    for key in ("gemma4", "qwen"):
        if key in local_cfg:
            router._local[key] = local_cfg[key]
        else:
            lp = MagicMock(spec=LocalOpenAIProvider)
            lp.available = False
            lp.name = key
            lp.complete = AsyncMock(side_effect=HTTPException(
                status_code=503,
                detail={"error_code": "LLM_NOT_CONFIGURED", "message": f"{key} not configured"},
            ))
            router._local[key] = lp
    return router


def _make_local(key: str, response: str | Exception) -> MagicMock:
    lp = MagicMock(spec=LocalOpenAIProvider)
    lp.available = True
    lp.name = key
    if isinstance(response, Exception):
        lp.complete = AsyncMock(side_effect=response)
    else:
        lp.complete = AsyncMock(return_value=response)
    return lp


def _make_gemini(response: str | Exception) -> AsyncMock:
    m = AsyncMock()
    m.name = "gemini"
    if isinstance(response, Exception):
        m.complete = AsyncMock(side_effect=response)
    else:
        m.complete = AsyncMock(return_value=response)
    return m


# ---------------------------------------------------------------------------
# _strip_think_tags
# ---------------------------------------------------------------------------

def test_strip_think_tags_removes_block():
    raw = "<think>internal reasoning here</think>Final answer."
    assert _strip_think_tags(raw) == "Final answer."


def test_strip_think_tags_multiline():
    raw = "<think>\nline1\nline2\n</think>  Answer text"
    assert _strip_think_tags(raw) == "Answer text"


def test_strip_think_tags_no_block():
    raw = "Normal answer without any tags."
    assert _strip_think_tags(raw) == raw


def test_strip_think_tags_case_insensitive():
    raw = "<THINK>hidden</THINK>visible"
    assert _strip_think_tags(raw) == "visible"


# ---------------------------------------------------------------------------
# LocalOpenAIProvider — unconfigured
# ---------------------------------------------------------------------------

def test_local_provider_unconfigured_marks_unavailable():
    lp = LocalOpenAIProvider(key="gemma4", base_url="", model_name="", api_key="")
    assert lp.available is False


@pytest.mark.asyncio
async def test_local_provider_unconfigured_raises_503():
    lp = LocalOpenAIProvider(key="gemma4", base_url="", model_name="", api_key="")
    with pytest.raises(HTTPException) as exc_info:
        await lp.complete("hello")
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error_code"] == "LLM_NOT_CONFIGURED"


# ---------------------------------------------------------------------------
# LLMRouter — Gemini success (no fallback)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gemini_success_no_fallback():
    gemini = _make_gemini("Gemini answer")
    router = make_router(gemini_provider=gemini)

    with patch.object(llm_mod, "get_llm_provider", return_value=gemini):
        result = await router.generate("question", model="auto")

    assert result["text"] == "Gemini answer"
    assert result["model_used"] == "gemini"
    assert result["fallback_used"] is False
    assert result["fallback_reason"] is None


# ---------------------------------------------------------------------------
# LLMRouter — Gemini 429 → fallback to Gemma4
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gemini_429_falls_back_to_gemma4():
    gemini = _make_gemini(
        HTTPException(status_code=429, detail={"error_code": "LLM_RATE_LIMITED", "message": "quota"})
    )
    gemma4 = _make_local("gemma4", "Gemma answer")
    router = make_router(gemini_provider=gemini, local_cfg={"gemma4": gemma4})

    with patch.object(llm_mod, "get_llm_provider", return_value=gemini):
        result = await router.generate("question", model="auto")

    assert result["text"] == "Gemma answer"
    assert result["model_used"] == "gemma4"
    assert result["fallback_used"] is True
    assert result["fallback_reason"] is not None


# ---------------------------------------------------------------------------
# LLMRouter — Gemma4 also down → falls back to Qwen
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gemini_and_gemma4_fail_falls_back_to_qwen():
    gemini = _make_gemini(
        HTTPException(status_code=503, detail={"error_code": "LLM_PROVIDER_ERROR", "message": "down"})
    )
    gemma4 = _make_local(
        "gemma4",
        HTTPException(status_code=503, detail={"error_code": "LLM_PROVIDER_OFFLINE", "message": "offline"}),
    )
    qwen = _make_local("qwen", "Qwen answer")
    router = make_router(gemini_provider=gemini, local_cfg={"gemma4": gemma4, "qwen": qwen})

    with patch.object(llm_mod, "get_llm_provider", return_value=gemini):
        result = await router.generate("question", model="auto")

    assert result["text"] == "Qwen answer"
    assert result["model_used"] == "qwen"
    assert result["fallback_used"] is True


# ---------------------------------------------------------------------------
# LLMRouter — all models fail → raises 503
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_models_fail_raises_503():
    gemini = _make_gemini(
        HTTPException(status_code=429, detail={"error_code": "LLM_RATE_LIMITED", "message": "quota"})
    )
    gemma4 = _make_local(
        "gemma4",
        HTTPException(status_code=503, detail={"error_code": "LLM_PROVIDER_OFFLINE", "message": "offline"}),
    )
    qwen = _make_local(
        "qwen",
        HTTPException(status_code=504, detail={"error_code": "LLM_TIMEOUT", "message": "timeout"}),
    )
    router = make_router(gemini_provider=gemini, local_cfg={"gemma4": gemma4, "qwen": qwen})

    with patch.object(llm_mod, "get_llm_provider", return_value=gemini):
        with pytest.raises(HTTPException) as exc_info:
            await router.generate("question", model="auto")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error_code"] == "LLM_ALL_FAILED"


# ---------------------------------------------------------------------------
# LLMRouter — explicit model selection (no silent fallback)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explicit_gemini_success():
    gemini = _make_gemini("Explicit Gemini")
    router = make_router(gemini_provider=gemini)

    with patch.object(llm_mod, "get_llm_provider", return_value=gemini):
        result = await router.generate("q", model="gemini")

    assert result["model_used"] == "gemini"
    assert result["fallback_used"] is False


@pytest.mark.asyncio
async def test_explicit_gemma4_success():
    gemini = _make_gemini("should not be called")
    gemma4 = _make_local("gemma4", "Gemma4 explicit")
    router = make_router(gemini_provider=gemini, local_cfg={"gemma4": gemma4})

    with patch.object(llm_mod, "get_llm_provider", return_value=gemini):
        result = await router.generate("q", model="gemma4")

    assert result["text"] == "Gemma4 explicit"
    assert result["model_used"] == "gemma4"
    assert result["fallback_used"] is False
    # Gemini must NOT have been called
    gemini.complete.assert_not_called()


# ---------------------------------------------------------------------------
# LLMRouter — circuit breaker cooldown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_circuit_breaker_skips_gemini_during_cooldown():
    gemini = _make_gemini("should not be reached")
    gemma4 = _make_local("gemma4", "Fallback while cooling")
    router = make_router(gemini_provider=gemini, local_cfg={"gemma4": gemma4})
    # Pre-trip the circuit breaker
    router._gemini_cooldown_until = time.monotonic() + 60.0

    with patch.object(llm_mod, "get_llm_provider", return_value=gemini):
        result = await router.generate("q", model="auto")

    assert result["model_used"] == "gemma4"
    assert result["fallback_used"] is True
    gemini.complete.assert_not_called()


@pytest.mark.asyncio
async def test_circuit_breaker_resets_after_gemini_success():
    gemini = _make_gemini("Recovered")
    router = make_router(gemini_provider=gemini)
    # Expire the cooldown
    router._gemini_cooldown_until = time.monotonic() - 1.0

    with patch.object(llm_mod, "get_llm_provider", return_value=gemini):
        result = await router.generate("q", model="auto")

    assert result["model_used"] == "gemini"
    assert router._gemini_cooldown_until == 0.0


# ---------------------------------------------------------------------------
# LLMRouter — non-transient error is NOT swallowed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_transient_error_propagates_immediately():
    """A 400 Bad Request from Gemini must NOT trigger fallback."""
    gemini = _make_gemini(
        HTTPException(status_code=400, detail={"error_code": "BAD_REQUEST", "message": "bad"})
    )
    gemma4 = _make_local("gemma4", "should not be reached")
    router = make_router(gemini_provider=gemini, local_cfg={"gemma4": gemma4})

    with patch.object(llm_mod, "get_llm_provider", return_value=gemini):
        with pytest.raises(HTTPException) as exc_info:
            await router.generate("q", model="auto")

    assert exc_info.value.status_code == 400
    gemma4.complete.assert_not_called()


# ---------------------------------------------------------------------------
# get_llm_router singleton
# ---------------------------------------------------------------------------

def test_get_llm_router_returns_same_instance():
    r1 = get_llm_router()
    r2 = get_llm_router()
    assert r1 is r2
