from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": settings.API_KEY}

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "bis-compliance-backend"}

def test_query_endpoint():
    payload = {"query": "Does QCO apply to imported plastic toys?"}
    response = client.post("/query", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] in ["compliance_check", "hybrid"]
    assert "detected_intent" in data["data"]

def test_compliance_check_integration():
    payload = {
        "category": "Footwear",
        "sub_category": "Leather Shoes",
        "description": "Safety boots made of genuine leather",
        "manufacturer_scale": "msme",
        "is_imported": False
    }
    response = client.post("/compliance/check", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()

    assert data["product"]["category"] == "Footwear"
    assert data["qco_result"]["applies"] is True
    assert data["qco_result"]["qco_id"] == "QCO-FOOTWEAR-2024"
    assert data["qco_result"]["exemption_status"] == "msme"
    assert len(data["requirements"]) > 0
    assert len(data["unverified_claims"]) == 0

def test_compliance_roadmap_integration():
    check_payload = {
        "category": "Toys",
        "description": "Plastic board game toy",
        "manufacturer_scale": "large",
        "is_imported": False
    }
    check_resp = client.post("/compliance/check", json=check_payload, headers=AUTH_HEADERS)
    assert check_resp.status_code == 200
    qco_result = check_resp.json()["qco_result"]

    roadmap_payload = {"qco_result": qco_result}
    roadmap_resp = client.post("/compliance/roadmap", json=roadmap_payload, headers=AUTH_HEADERS)
    assert roadmap_resp.status_code == 200
    roadmap_data = roadmap_resp.json()

    assert roadmap_data["qco_id"] == "QCO-TOYS-2020"
    assert len(roadmap_data["steps"]) >= 4
    assert roadmap_data["steps"][0]["step_number"] == 1
