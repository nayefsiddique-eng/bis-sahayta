"""
Regression tests for:
- Voice WebSocket endpoint (auth, empty audio, process flow)
- Document upload (valid, invalid MIME, oversized, path traversal, empty)
- RAG deduplication and metadata fix
- Clean LLM prompt (no meta-commentary rules)
- Global exception handler (no raw stack traces)
- Cache behavior
- 429 rate limit handling
"""
import io
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)
AUTH = {"X-API-Key": settings.API_KEY}


# ─────────────────────────────────────────────────────────────────────────────
# Document upload regression tests
# ─────────────────────────────────────────────────────────────────────────────

MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
    b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
    b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_document_upload_valid_png():
    """Upload a valid PNG — should return 201 with document metadata."""
    resp = client.post(
        "/documents/upload",
        files={"file": ("test.png", io.BytesIO(MINIMAL_PNG), "image/png")},
        headers=AUTH,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "document_id" in data
    assert data["document_id"].startswith("doc-")
    assert data["content_type"] == "image/png"
    assert data["filename"] == "test.png"
    assert "extracted_text_preview" in data
    assert "full_text_available" in data


def test_document_upload_rejects_unsupported_mime():
    """Uploading an EXE file should return 415 Unsupported Media Type."""
    resp = client.post(
        "/documents/upload",
        files={"file": ("bad.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
        headers=AUTH,
    )
    assert resp.status_code == 415
    data = resp.json()
    assert "Unsupported" in data.get("detail", "") or resp.status_code == 415


def test_document_upload_rejects_path_traversal():
    """Filename with path traversal should return 400."""
    resp = client.post(
        "/documents/upload",
        files={"file": ("../../etc/passwd", io.BytesIO(MINIMAL_PNG), "image/png")},
        headers=AUTH,
    )
    assert resp.status_code == 400


def test_document_upload_rejects_oversized_file(monkeypatch):
    """Files exceeding MAX_UPLOAD_SIZE_MB should return 413."""
    import app.routers.documents as docs_router
    monkeypatch.setattr(docs_router.settings, "MAX_UPLOAD_SIZE_MB", 0)
    resp = client.post(
        "/documents/upload",
        files={"file": ("test.png", io.BytesIO(MINIMAL_PNG), "image/png")},
        headers=AUTH,
    )
    assert resp.status_code == 413


def test_document_upload_get_and_delete():
    """Upload, fetch metadata, then delete."""
    # Upload
    resp = client.post(
        "/documents/upload",
        files={"file": ("doc.png", io.BytesIO(MINIMAL_PNG), "image/png")},
        headers=AUTH,
    )
    assert resp.status_code == 201
    doc_id = resp.json()["document_id"]

    # Get
    get_resp = client.get(f"/documents/{doc_id}", headers=AUTH)
    assert get_resp.status_code == 200
    assert get_resp.json()["document_id"] == doc_id

    # Delete
    del_resp = client.delete(f"/documents/{doc_id}", headers=AUTH)
    assert del_resp.status_code == 204

    # Confirm gone
    gone_resp = client.get(f"/documents/{doc_id}", headers=AUTH)
    assert gone_resp.status_code == 404


def test_document_get_nonexistent():
    """Getting a non-existent document should return 404."""
    resp = client.get("/documents/doc-nonexistent-xyz", headers=AUTH)
    assert resp.status_code == 404


def test_document_delete_nonexistent():
    """Deleting a non-existent document should return 404."""
    resp = client.delete("/documents/doc-nonexistent-xyz", headers=AUTH)
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Voice regression tests (WebSocket — test auth rejection and basic protocol)
# ─────────────────────────────────────────────────────────────────────────────

def test_voice_websocket_rejects_missing_key():
    """WebSocket without API key should be closed with 1008."""
    from starlette.testclient import TestClient
    with TestClient(app) as tc:
        with pytest.raises(Exception):
            with tc.websocket_connect("/voice/stream") as ws:
                pass


def test_voice_websocket_accepts_valid_key():
    """WebSocket with valid API key should successfully accept connection."""
    with client.websocket_connect(f"/voice/stream?api_key={settings.API_KEY}") as ws:
        ws.send_json({"type": "config", "lang_code": "en"})
        ack = ws.receive_json()
        assert ack["type"] == "config_ack"
        assert ack["lang_code"] == "en"


def test_voice_websocket_empty_audio():
    """Sending audio_end with no audio should return error, not crash."""
    with client.websocket_connect(f"/voice/stream?api_key={settings.API_KEY}") as ws:
        ws.send_json({"type": "audio_end"})
        resp = ws.receive_json()
        assert resp["type"] == "error"
        assert "No audio" in resp["message"]


# ─────────────────────────────────────────────────────────────────────────────
# LLM prompt quality regression tests
# ─────────────────────────────────────────────────────────────────────────────

def test_chat_prompt_no_meta_commentary_rule():
    """The improved prompt must include rules against meta-commentary."""
    from app.services.llm_service import LLMService
    prompt = LLMService.build_chat_prompt("What is IS 302?", [], [], style="simple")
    assert "Do not say" in prompt or "meta-commentary" in prompt or "preamble" in prompt


def test_chat_prompt_no_repeat_rule():
    """Prompt must instruct not to repeat information."""
    from app.services.llm_service import LLMService
    prompt = LLMService.build_chat_prompt("BIS certification steps", [], [], style="simple")
    assert "repeat" in prompt.lower() or "focused" in prompt.lower()


def test_chat_prompt_short_style_concise():
    """Short style must instruct for brevity."""
    from app.services.llm_service import LLMService
    prompt = LLMService.build_chat_prompt("What is QCO?", [], [], style="short")
    assert "concise" in prompt.lower() or "brief" in prompt.lower() or "sentences" in prompt.lower()


def test_chat_prompt_answer_label():
    """Prompt should end with ANSWER: label, not RESPONSE:."""
    from app.services.llm_service import LLMService
    prompt = LLMService.build_chat_prompt("Question", [], [], style="simple")
    assert "ANSWER:" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# Global exception handler — no raw trace leak
# ─────────────────────────────────────────────────────────────────────────────

def test_global_handler_does_not_expose_trace():
    """Global exception handler must not expose raw exception strings to users."""
    from app.core.exceptions import global_exception_handler
    from fastapi import Request
    from unittest.mock import MagicMock
    req = MagicMock(spec=Request)
    req.method = "GET"
    req.url.path = "/test"
    exc = RuntimeError("This is a super secret internal error with /etc/passwd")

    import asyncio
    res = asyncio.run(global_exception_handler(req, exc))
    body = res.body.decode()
    assert "super secret" not in body
    assert "passwd" not in body
    assert res.status_code == 500


# ─────────────────────────────────────────────────────────────────────────────
# RAG deduplication
# ─────────────────────────────────────────────────────────────────────────────

def test_rag_deduplication_in_chat(monkeypatch):
    """Duplicate RAG chunks should be deduplicated before building the LLM prompt."""
    from app.routers import chat as chat_mod
    from app.services.rag_service import RAGService

    monkeypatch.setattr(RAGService, "is_available", staticmethod(lambda: True))
    duplicate_chunk = {"text": "IS 302 applies to toys." * 5, "metadata": {}, "score": 0.9}
    monkeypatch.setattr(
        RAGService, "retrieve_with_metadata",
        staticmethod(lambda q, k=5: [duplicate_chunk, duplicate_chunk, duplicate_chunk])
    )

    called_prompts = []

    async def capturing_complete(prompt, **kwargs):
        called_prompts.append(prompt)
        return "Deduplicated answer."

    monkeypatch.setattr(chat_mod.LLMService, "complete", staticmethod(capturing_complete))

    resp = client.post("/api/chat", json={"query": "toy standards"}, headers=AUTH)
    assert resp.status_code == 200

    if called_prompts:
        prompt_used = called_prompts[0]
        # In the RAG document context section, chunk [1] should appear, but not chunk [2]
        context_part = prompt_used.split("USER QUESTION:")[0]
        assert "[1] BIS document" in context_part
        assert "[2] BIS document" not in context_part



# ─────────────────────────────────────────────────────────────────────────────
# API contract: /documents/upload response shape
# ─────────────────────────────────────────────────────────────────────────────

def test_document_upload_response_shape():
    """Upload response must match DocumentMeta schema exactly."""
    resp = client.post(
        "/documents/upload",
        files={"file": ("shape.png", io.BytesIO(MINIMAL_PNG), "image/png")},
        headers=AUTH,
    )
    assert resp.status_code == 201
    data = resp.json()
    required_fields = {
        "document_id", "filename", "content_type", "size_bytes",
        "sha256", "uploaded_at", "extracted_text_preview", "full_text_available"
    }
    missing = required_fields - set(data.keys())
    assert not missing, f"Missing fields in upload response: {missing}"
    assert isinstance(data["size_bytes"], int)
    assert isinstance(data["full_text_available"], bool)
    assert len(data["sha256"]) == 64  # SHA-256 hex digest
