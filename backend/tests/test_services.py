"""
Tests for LLM service abstraction, OCR service, RAG service, cache service,
and flashcard generation — all using mock providers (no external calls).
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock


# ─────────────────────────────────────────────────────────────────────────────
# LLM Service
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_provider_returns_string():
    from app.services.llm_service import MockProvider
    provider = MockProvider()
    result = await provider.complete("What is BIS?")
    assert isinstance(result, str)
    assert len(result) > 0
    assert "[MockLLM]" in result


def test_mock_provider_name():
    from app.services.llm_service import MockProvider
    assert MockProvider().name == "mock"


def test_get_llm_provider_mock_default(monkeypatch):
    """With LLM_PROVIDER=mock, factory should return MockProvider."""
    import app.services.llm_service as llm_mod
    llm_mod._provider_instance = None  # reset singleton
    monkeypatch.setattr("app.core.config.settings.LLM_PROVIDER", "mock")
    provider = llm_mod.get_llm_provider()
    assert provider.name == "mock"
    llm_mod._provider_instance = None  # cleanup


@pytest.mark.asyncio
async def test_llm_service_complete_with_mock():
    from app.services.llm_service import LLMService, MockProvider
    result = await LLMService.complete("Tell me about IS 2082", provider=MockProvider())
    assert isinstance(result, str)
    assert len(result) > 10


def test_build_rag_prompt():
    from app.services.llm_service import LLMService
    prompt = LLMService.build_rag_prompt(
        "What is IS 1234?",
        ["Chunk 1: IS 1234 deals with cement.", "Chunk 2: Requirements include..."],
    )
    assert "IS 1234" in prompt
    assert "CONTEXT" in prompt
    assert "QUESTION" in prompt


def test_build_chat_prompt_with_history():
    from app.services.llm_service import LLMService
    prompt = LLMService.build_chat_prompt(
        question="What lab should I use?",
        context_chunks=["NABL accredited labs are listed in QCO."],
        history=[{"user": "What is QCO?", "assistant": "QCO stands for Quality Control Order."}],
        session_context="category: Toys",
    )
    assert "lab" in prompt.lower()
    assert "QCO" in prompt
    assert "SESSION CONTEXT" in prompt
    assert "CONVERSATION HISTORY" in prompt


def test_build_chat_prompt_styles():
    from app.services.llm_service import LLMService
    prompt_short = LLMService.build_chat_prompt("What is IS 302?", [], [], style="short")
    prompt_tech = LLMService.build_chat_prompt("What is IS 302?", [], [], style="technical")
    assert "concise" in prompt_short.lower()
    assert "technical" in prompt_tech.lower()
    assert prompt_short != prompt_tech


# ─────────────────────────────────────────────────────────────────────────────
# OCR Service
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_ocr_provider():
    from app.services.ocr_service import MockOCRProvider
    provider = MockOCRProvider()
    text = await provider.extract_text(b"fake-image-bytes", lang="eng")
    assert isinstance(text, str)
    assert "[MockOCR]" in text


@pytest.mark.asyncio
async def test_ocr_service_image():
    from app.services.ocr_service import OCRService, MockOCRProvider
    # Force mock provider
    import app.services.ocr_service as ocr_mod
    ocr_mod._ocr_provider = MockOCRProvider()
    result = await OCRService.extract_text(b"image-bytes", mime_type="image/jpeg")
    assert isinstance(result, str)
    ocr_mod._ocr_provider = None  # cleanup


@pytest.mark.asyncio
async def test_ocr_service_pdf_fallback_to_ocr():
    """When PDF has no embedded text, should fall back to OCR (mock returns placeholder)."""
    from app.services.ocr_service import OCRService, MockOCRProvider
    import app.services.ocr_service as ocr_mod
    ocr_mod._ocr_provider = MockOCRProvider()
    # Pass a short byte string that is NOT a valid PDF (so extract_text_from_pdf returns "")
    result = await OCRService.extract_text(b"not-a-real-pdf", mime_type="application/pdf")
    # Should fall through to OCR and return mock text
    assert isinstance(result, str)
    ocr_mod._ocr_provider = None


# ─────────────────────────────────────────────────────────────────────────────
# Cache Service
# ─────────────────────────────────────────────────────────────────────────────

def test_in_memory_cache_set_get():
    from app.services.cache_service import _InMemoryCache
    cache = _InMemoryCache()
    cache.set("key1", {"value": 42})
    result = cache.get("key1")
    assert result == {"value": 42}


def test_in_memory_cache_miss():
    from app.services.cache_service import _InMemoryCache
    cache = _InMemoryCache()
    assert cache.get("nonexistent") is None


def test_in_memory_cache_delete():
    from app.services.cache_service import _InMemoryCache
    cache = _InMemoryCache()
    cache.set("k", "v")
    cache.delete("k")
    assert cache.get("k") is None


def test_make_cache_key_deterministic():
    from app.services.cache_service import make_cache_key
    key1 = make_cache_key("toys", "large", True, prefix="test")
    key2 = make_cache_key("toys", "large", True, prefix="test")
    assert key1 == key2
    assert key1.startswith("test:")


def test_make_cache_key_different_inputs():
    from app.services.cache_service import make_cache_key
    key1 = make_cache_key("toys", prefix="a")
    key2 = make_cache_key("footwear", prefix="a")
    assert key1 != key2


# ─────────────────────────────────────────────────────────────────────────────
# Session DB
# ─────────────────────────────────────────────────────────────────────────────

def test_session_create_and_retrieve():
    from app.services.session_db import create_session, get_session
    session = create_session(context={"product": "test"})
    assert "session_id" in session
    retrieved = get_session(session["session_id"])
    assert retrieved is not None
    assert retrieved["context"]["product"] == "test"


def test_session_not_found():
    from app.services.session_db import get_session
    assert get_session("totally-invalid-id-xyz") is None


def test_add_and_get_messages():
    from app.services.session_db import create_session, add_message, get_history
    session = create_session()
    sid = session["session_id"]
    add_message(sid, "user", "What is BIS?")
    add_message(sid, "assistant", "BIS is Bureau of Indian Standards.")
    history = get_history(sid)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


def test_get_history_as_pairs():
    from app.services.session_db import create_session, add_message, get_history_as_pairs
    session = create_session()
    sid = session["session_id"]
    add_message(sid, "user", "Q1")
    add_message(sid, "assistant", "A1")
    add_message(sid, "user", "Q2")
    add_message(sid, "assistant", "A2")
    pairs = get_history_as_pairs(sid)
    assert len(pairs) == 2
    assert pairs[0]["user"] == "Q1"
    assert pairs[0]["assistant"] == "A1"


# ─────────────────────────────────────────────────────────────────────────────
# Flashcard Service
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_flashcard_generation_mock():
    from app.services.flashcard_service import generate_flashcards
    from app.services.llm_service import MockProvider
    cards = await generate_flashcards("BIS certification for toys", num_cards=5, provider=MockProvider())
    assert isinstance(cards, list)
    assert len(cards) >= 1
    for card in cards:
        assert "question" in card
        assert "answer" in card


@pytest.mark.asyncio
async def test_flashcard_respects_num_cards_cap():
    from app.services.flashcard_service import generate_flashcards
    from app.services.llm_service import MockProvider
    # Request more than 20 — service should cap internally
    cards = await generate_flashcards("BIS", num_cards=25, provider=MockProvider())
    assert isinstance(cards, list)
    assert len(cards) <= 20


# ─────────────────────────────────────────────────────────────────────────────
# RAG Service
# ─────────────────────────────────────────────────────────────────────────────

def test_rag_service_availability():
    """RAGService.is_available() must return bool without crashing."""
    from app.services.rag_service import RAGService
    result = RAGService.is_available()
    assert isinstance(result, bool)


def test_rag_service_retrieve_returns_list_when_unavailable():
    """When FAISS index doesn't exist, retrieve() should return empty list, not crash."""
    from app.services.rag_service import RAGService
    if not RAGService.is_available():
        results = RAGService.retrieve("test query")
        assert isinstance(results, list)
        assert len(results) == 0
    else:
        # If available, check return type
        results = RAGService.retrieve("BIS toy standards")
        assert isinstance(results, list)


def test_rag_retrieve_texts():
    from app.services.rag_service import RAGService
    texts = RAGService.retrieve_texts("cement BIS standard")
    assert isinstance(texts, list)
    for t in texts:
        assert isinstance(t, str)


def test_rag_retrieves_real_chunks():
    import pytest
    from app.services.rag_service import RAGService
    if not RAGService.is_available():
        pytest.skip("vector store not present")
    chunks = RAGService.retrieve_with_metadata("household electrical appliances safety", k=3)
    assert len(chunks) == 3
    assert chunks[0]["text"]
    assert chunks[0]["score"] > 0.4


def test_build_chat_prompt_grounding():
    from app.services.llm_service import LLMService
    with_ctx = LLMService.build_chat_prompt("q", ["[1] IS 2082, page 1: text"], [], style="simple")
    no_ctx = LLMService.build_chat_prompt("q", [], [], style="simple")
    assert "Cite them inline" in with_ctx
    assert "not verified" in no_ctx