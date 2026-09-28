import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.cache import response_cache
from app.core.rate_limiter import rate_limiter

client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": settings.API_KEY}

def setup_function():
    response_cache.clear()
    rate_limiter._store.clear()

def test_unauthorized_access_step10():
    # Calling protected endpoint without X-API-Key should return 401
    response = client.get("/languages/supported")
    assert response.status_code == 401
    data = response.json()
    assert data["error_code"] == "UNAUTHORIZED"
    assert "X-API-Key" in data["message"]

def test_health_endpoint_public_bypass():
    # Health endpoint should be publicly accessible without API Key
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_structured_error_validation_step1():
    # Sending invalid payload to compliance check should return 422 with structured schema
    response = client.post("/compliance/check", json={"invalid_field": 123}, headers=AUTH_HEADERS)
    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "INVALID_PRODUCT_INPUT"
    assert "detail" in data

def test_request_id_correlation_step2():
    response = client.get("/languages/supported", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0

def test_response_caching_step3():
    payload = {
        "category": "Toys",
        "description": "Plastic toy action figure",
        "manufacturer_scale": "large"
    }

    # First request - uncached
    res1 = client.post("/compliance/check", json=payload, headers=AUTH_HEADERS)
    assert res1.status_code == 200

    # Second request - should serve from cache
    res2 = client.post("/compliance/check", json=payload, headers=AUTH_HEADERS)
    assert res2.status_code == 200
    assert res1.json() == res2.json()

def test_rate_limiting_step4():
    payload = {"query": "Test query for rate limit"}
    headers = {"X-API-Key": settings.API_KEY, "REMOTE_ADDR": "192.168.1.100"}

    # Consume allowed 10 requests
    for _ in range(10):
        client.post("/translate/text", json={"text": "hi", "source_lang": "en", "target_lang": "hi"}, headers=headers)

    # 11th request should be rate limited
    res = client.post("/translate/text", json={"text": "hi", "source_lang": "en", "target_lang": "hi"}, headers=headers)
    assert res.status_code == 429
    data = res.json()
    assert data["error_code"] == "RATE_LIMITED"
    assert "Retry-After" in res.headers

def test_confidence_scoring_high_and_low_step5():
    # 1. High confidence exact category match
    exact_product = {
        "category": "Toys",
        "description": "Board game for kids",
        "manufacturer_scale": "large"
    }
    res_exact = client.post("/compliance/check", json=exact_product, headers=AUTH_HEADERS)
    assert res_exact.status_code == 200
    data_exact = res_exact.json()
    assert data_exact["qco_result"]["confidence"] >= 0.9
    assert data_exact["low_confidence_warning"] is False

    # 2. Low confidence fuzzy description match
    fuzzy_product = {
        "category": "Random Household Gadget",
        "description": "Contains minor plastic toys parts",
        "manufacturer_scale": "large"
    }
    res_fuzzy = client.post("/compliance/check", json=fuzzy_product, headers=AUTH_HEADERS)
    assert res_fuzzy.status_code == 200
    data_fuzzy = res_fuzzy.json()
    assert data_fuzzy["qco_result"]["confidence"] < 0.6
    assert data_fuzzy["low_confidence_warning"] is True

def test_multi_standard_support_step6():
    # Category with keywords matching both Footwear and Steel Products
    multi_product = {
        "category": "Footwear",
        "description": "Safety leather footwear with stainless steel toe cap reinforcement",
        "manufacturer_scale": "large"
    }
    res = client.post("/compliance/check", json=multi_product, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()

    assert "qco_results" in data
    assert len(data["qco_results"]) >= 2
    matched_qco_ids = [r["qco_id"] for r in data["qco_results"]]
    assert "QCO-FOOTWEAR-2024" in matched_qco_ids
    assert "QCO-STEEL-2023" in matched_qco_ids

def test_standards_version_history_step7():
    res = client.get("/standards/IS%2017043:2018/history", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["standard_id"] == "IS 17043:2018"
    assert len(data["history"]) >= 2
    assert "effective_date" in data["history"][0]

def test_feedback_endpoint_step8():
    payload = {
        "request_id": "req-12345",
        "verdict_correct": True,
        "comment": "Accurate QCO identification for footwear standard."
    }
    res = client.post("/feedback", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "feedback_id" in data

def test_explain_mode_step9():
    payload = {
        "category": "Footwear",
        "description": "Leather boots",
        "manufacturer_scale": "large"
    }
    # Non-explain request
    res_no_explain = client.post("/compliance/check", json=payload, headers=AUTH_HEADERS)
    assert res_no_explain.json()["explanation"] is None

    # Explain request
    res_explain = client.post("/compliance/check?explain=true", json=payload, headers=AUTH_HEADERS)
    data = res_explain.json()
    assert data["explanation"] is not None
    assert "candidates_evaluated" in data["explanation"]
    assert "rejected_candidates" in data["explanation"]
