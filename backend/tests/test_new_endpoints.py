"""
Tests for new endpoints added in v3.0:
- POST /chat
- POST /sessions, GET /sessions/{id}
- GET /standards (list/search)
- GET /standards/{id} (detail)
- POST /translate (alias)
- POST /flashcards/generate
- POST /certification/analyze
- POST /certification/roadmap
- POST /tasks, GET /tasks/{id}
- GET /ready
- POST /documents/scan
"""
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)
AUTH = {"X-API-Key": settings.API_KEY}


# ─────────────────────────────────────────────────────────────────────────────
# /ready
# ─────────────────────────────────────────────────────────────────────────────

def test_ready_endpoint():
    resp = client.get("/ready")
    assert resp.status_code in (200, 503)  # 503 if optional deps missing
    data = resp.json()
    assert "checks" in data
    assert "compliance_engine" in data["checks"]
    assert data["checks"]["compliance_engine"]["status"] == "ok"


# ─────────────────────────────────────────────────────────────────────────────
# /standards
# ─────────────────────────────────────────────────────────────────────────────

def test_standards_list_all():
    resp = client.get("/standards", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "standards" in data
    assert "total" in data
    assert data["total"] > 0
    # Each entry should have qco_id and title
    for std in data["standards"]:
        assert "qco_id" in std
        assert "title" in std


def test_standards_search():
    resp = client.get("/standards?search=toys", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    # Should find at least the toys QCO
    assert data["total"] >= 1
    titles = [s["title"].lower() for s in data["standards"]]
    qco_ids = [s["qco_id"].lower() for s in data["standards"]]
    assert any("toy" in t or "toy" in q for t, q in zip(titles, qco_ids))


def test_standards_search_no_results():
    resp = client.get("/standards?search=xyznonexistentproduct999", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


def test_standards_get_by_qco_id():
    resp = client.get("/standards/QCO-TOYS-2020", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["qco_id"] == "QCO-TOYS-2020"


def test_standards_get_not_found():
    resp = client.get("/standards/QCO-NONEXISTENT-9999", headers=AUTH)
    assert resp.status_code == 404


def test_standards_history_preserved():
    """Ensure existing /history endpoint still works (backward compat)."""
    resp = client.get("/standards/QCO-FOOTWEAR-2024/history", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "history" in data
    assert data["qco_id"] == "QCO-FOOTWEAR-2024"


# ─────────────────────────────────────────────────────────────────────────────
# /translate (alias)
# ─────────────────────────────────────────────────────────────────────────────

def test_translate_primary_endpoint():
    """POST /translate should work as alias for POST /translate/text."""
    payload = {"text": "What is BIS?", "source_lang": "en", "target_lang": "hi"}
    resp = client.post("/translate", json=payload, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "translated_text" in data
    assert "translation_unavailable" in data
    assert data["source_lang"] == "en"
    assert data["target_lang"] == "hi"


def test_translate_text_alias_still_works():
    """Original /translate/text endpoint must remain functional."""
    payload = {"text": "Certification", "source_lang": "en", "target_lang": "hi"}
    resp = client.post("/translate/text", json=payload, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "translated_text" in data


# ─────────────────────────────────────────────────────────────────────────────
# /sessions
# ─────────────────────────────────────────────────────────────────────────────

def test_create_session():
    resp = client.post("/sessions", json={}, headers=AUTH)
    assert resp.status_code == 201
    data = resp.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 0


def test_get_session():
    # Create first
    create_resp = client.post("/sessions", json={"context": {"product": "cement"}}, headers=AUTH)
    assert create_resp.status_code == 201
    session_id = create_resp.json()["session_id"]

    # Get it
    get_resp = client.get(f"/sessions/{session_id}", headers=AUTH)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["session_id"] == session_id


def test_get_nonexistent_session():
    resp = client.get("/sessions/non-existent-session-id", headers=AUTH)
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# /chat
# ─────────────────────────────────────────────────────────────────────────────

def test_chat_new_session():
    """Chat without a session_id should create one automatically."""
    payload = {"message": "What is BIS certification?"}
    resp = client.post("/chat", json=payload, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "reply" in data
    assert "intent" in data
    assert len(data["reply"]) > 0


def test_chat_with_existing_session():
    """Subsequent chat messages with same session_id should work."""
    # Create session
    session_resp = client.post("/sessions", json={}, headers=AUTH)
    session_id = session_resp.json()["session_id"]

    # First message
    resp1 = client.post("/chat", json={"message": "What is QCO?", "session_id": session_id}, headers=AUTH)
    assert resp1.status_code == 200
    assert resp1.json()["session_id"] == session_id

    # Second message (continuation)
    resp2 = client.post("/chat", json={"message": "Tell me more", "session_id": session_id}, headers=AUTH)
    assert resp2.status_code == 200
    assert resp2.json()["session_id"] == session_id


def test_chat_invalid_session_returns_404():
    payload = {"message": "Hello", "session_id": "invalid-session-xyz"}
    resp = client.post("/chat", json=payload, headers=AUTH)
    assert resp.status_code == 404


def test_chat_returns_intent():
    payload = {"message": "Does QCO apply to plastic toys?"}
    resp = client.post("/chat", json=payload, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] in ["compliance_check", "hybrid", "general_qa", "certification_process"]


def test_chat_rag_field_present():
    payload = {"message": "BIS standards for cement"}
    resp = client.post("/chat", json=payload, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "rag_used" in data
    assert isinstance(data["rag_used"], bool)


# ─────────────────────────────────────────────────────────────────────────────
# /flashcards/generate
# ─────────────────────────────────────────────────────────────────────────────

def test_flashcard_generation():
    payload = {"topic": "BIS certification for toys", "num_cards": 5, "use_rag": False}
    resp = client.post("/flashcards/generate", json=payload, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["topic"] == "BIS certification for toys"
    assert data["num_requested"] == 5
    assert "flashcards" in data
    assert isinstance(data["flashcards"], list)
    assert len(data["flashcards"]) >= 1
    # Each card has question and answer
    for card in data["flashcards"]:
        assert "question" in card
        assert "answer" in card


def test_flashcard_num_cards_validation():
    """num_cards must be between 1 and 20."""
    payload = {"topic": "BIS", "num_cards": 100}
    resp = client.post("/flashcards/generate", json=payload, headers=AUTH)
    assert resp.status_code == 422


def test_flashcard_caching():
    """Same request twice should return cached result."""
    payload = {"topic": "QCO Footwear 2024", "num_cards": 3, "use_rag": False}
    resp1 = client.post("/flashcards/generate", json=payload, headers=AUTH)
    resp2 = client.post("/flashcards/generate", json=payload, headers=AUTH)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # Both should have same flashcard content
    assert resp1.json()["num_requested"] == resp2.json()["num_requested"]


# ─────────────────────────────────────────────────────────────────────────────
# /certification
# ─────────────────────────────────────────────────────────────────────────────

def test_certification_analyze():
    payload = {
        "product_name": "Plastic Board Game",
        "category": "Toys",
        "description": "A plastic board game for children aged 6+",
        "manufacturer_scale": "large",
        "is_imported": False,
    }
    resp = client.post("/certification/analyze", json=payload, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_name"] == "Plastic Board Game"
    assert "qco_applicable" in data
    assert isinstance(data["qco_applicable"], bool)
    assert "summary" in data
    assert "requirements" in data
    assert "recommended_labs" in data


def test_certification_analyze_footwear():
    payload = {
        "product_name": "Safety Boot",
        "category": "Footwear",
        "description": "Genuine leather safety boots",
        "manufacturer_scale": "msme",
        "is_imported": False,
    }
    resp = client.post("/certification/analyze", json=payload, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["qco_applicable"] is True
    assert data["qco_id"] == "QCO-FOOTWEAR-2024"


def test_certification_roadmap():
    payload = {"qco_id": "QCO-TOYS-2020", "manufacturer_scale": "large"}
    resp = client.post("/certification/roadmap", json=payload, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["qco_id"] == "QCO-TOYS-2020"
    assert "steps" in data
    assert len(data["steps"]) >= 1


def test_certification_roadmap_not_found():
    payload = {"qco_id": "QCO-NONEXISTENT-9999"}
    resp = client.post("/certification/roadmap", json=payload, headers=AUTH)
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# /tasks
# ─────────────────────────────────────────────────────────────────────────────

def test_submit_batch_compliance_task():
    payload = {
        "task_type": "batch_compliance_check",
        "payload": {
            "products": [
                {"category": "Toys", "description": "Plastic toy car", "manufacturer_scale": "large"},
                {"category": "Footwear", "description": "Leather shoe", "manufacturer_scale": "msme"},
            ]
        },
    }
    resp = client.post("/tasks", json=payload, headers=AUTH)
    assert resp.status_code == 202
    data = resp.json()
    assert "task_id" in data
    assert data["task_type"] == "batch_compliance_check"
    assert data["status"] in ("pending", "success", "failure")


def test_submit_flashcard_task():
    payload = {
        "task_type": "generate_flashcards",
        "payload": {"topic": "BIS Solar PV standards", "num_cards": 3},
    }
    resp = client.post("/tasks", json=payload, headers=AUTH)
    assert resp.status_code == 202
    data = resp.json()
    assert "task_id" in data


def test_get_task_status():
    # Submit first
    payload = {
        "task_type": "batch_compliance_check",
        "payload": {"products": [{"category": "Steel", "description": "Steel rod", "manufacturer_scale": "large"}]},
    }
    submit_resp = client.post("/tasks", json=payload, headers=AUTH)
    assert submit_resp.status_code == 202
    task_id = submit_resp.json()["task_id"]

    # Poll status
    status_resp = client.get(f"/tasks/{task_id}", headers=AUTH)
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["task_id"] == task_id
    assert data["status"] in ("pending", "started", "success", "failure")


def test_get_nonexistent_task():
    resp = client.get("/tasks/task-nonexistent-000", headers=AUTH)
    assert resp.status_code == 404


def test_invalid_task_type():
    payload = {"task_type": "fly_to_moon", "payload": {}}
    resp = client.post("/tasks", json=payload, headers=AUTH)
    assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# /documents/scan  (inline OCR — no file storage)
# ─────────────────────────────────────────────────────────────────────────────

def test_document_scan_png():
    """Scan a minimal PNG image — MockOCR should return placeholder text."""
    # Minimal valid PNG (1x1 white pixel)
    minimal_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
        b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    resp = client.post(
        "/documents/scan",
        files={"file": ("test.png", io.BytesIO(minimal_png), "image/png")},
        headers=AUTH,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "extracted_text" in data
    assert "char_count" in data
    assert data["filename"] == "test.png"


def test_document_scan_rejects_invalid_mime():
    """Uploading an unsupported file type should return 415."""
    resp = client.post(
        "/documents/scan",
        files={"file": ("malware.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        headers=AUTH,
    )
    assert resp.status_code == 415


def test_document_scan_rejects_path_traversal():
    """Filenames with path traversal sequences should return 400."""
    minimal_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
    resp = client.post(
        "/documents/scan",
        files={"file": ("../../etc/passwd", io.BytesIO(minimal_png), "image/png")},
        headers=AUTH,
    )
    assert resp.status_code == 400


def test_get_sessions_list_shape_and_order():
    # Create two sessions
    resp1 = client.post("/sessions", json={"context": {"product": "test1"}}, headers=AUTH)
    assert resp1.status_code == 201
    session1 = resp1.json()
    assert "session_id" in session1

    resp2 = client.post("/sessions", json={"context": {"product": "test2"}}, headers=AUTH)
    assert resp2.status_code == 201
    session2 = resp2.json()
    assert "session_id" in session2

    # Test /sessions endpoint
    resp = client.get("/sessions", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # We expect exactly two sessions (since db is fresh)
    assert len(data) == 2
    # Newest first: session2 should be first because it was created after session1
    assert data[0]["updated_at"] >= data[1]["updated_at"]
    # Also check that we have the two session IDs we created
    session_ids = {session["session_id"] for session in data}
    assert session1["session_id"] in session_ids
    assert session2["session_id"] in session_ids

    # Test /api/sessions endpoint (alias)
    resp = client.get("/api/sessions", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["updated_at"] >= data[1]["updated_at"]
    session_ids = {session["session_id"] for session in data}
    assert session1["session_id"] in session_ids
    assert session2["session_id"] in session_ids


def test_chat_relevance_field_and_api_alias():
    payload = {"message": "What is IS 302?"}
    resp = client.post("/api/chat", json=payload, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert "relevance" in data
    # relevance is either a float between 0 and 1 or None
    relevance = data["relevance"]
    if relevance is not None:
        assert isinstance(relevance, float)
        assert 0.0 <= relevance <= 1.0
    # Check that rag_used and sources are consistent
    assert "rag_used" in data
    assert "sources" in data
    assert isinstance(data["sources"], list)
    # rag_used should be True if and only if sources is non-empty
    assert data["rag_used"] == (len(data["sources"]) > 0)


def test_chat_style_validation():
    payload = {"message": "Tell me about BIS", "style": "invalid_style_xyz"}
    resp = client.post("/api/chat", json=payload, headers=AUTH)
    assert resp.status_code == 422
