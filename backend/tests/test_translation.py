from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services.translation import BhashiniUnavailableError

client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": settings.API_KEY}

def test_supported_languages_endpoint():
    response = client.get("/languages/supported", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "languages" in data
    codes = [l["code"] for l in data["languages"]]
    assert "hi" in codes
    assert "en" in codes

@patch("app.routers.translate.translate_text", new_callable=AsyncMock)
def test_translate_text_success(mock_translate):
    mock_translate.return_value = "खिलौने गुणवत्ता नियंत्रण आदेश"

    payload = {
        "text": "Toys Quality Control Order",
        "source_lang": "en",
        "target_lang": "hi"
    }
    response = client.post("/translate/text", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["translated_text"] == "खिलौने गुणवत्ता नियंत्रण आदेश"
    assert data["translation_unavailable"] is False

@patch("app.routers.translate.translate_text", new_callable=AsyncMock)
def test_translate_text_fallback_on_bhashini_failure(mock_translate):
    mock_translate.side_effect = BhashiniUnavailableError("Service Offline")

    payload = {
        "text": "Toys Quality Control Order",
        "source_lang": "en",
        "target_lang": "hi"
    }
    response = client.post("/translate/text", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["translated_text"] == "Toys Quality Control Order"
    assert data["translation_unavailable"] is True

@patch("app.routers.compliance.translate_text", new_callable=AsyncMock)
def test_compliance_check_multilingual_structured_preservation(mock_translate):
    async def side_effect_translate(text, source_lang, target_lang):
        if source_lang == "hi" and target_lang == "en":
            if "जूते" in text or "footwear" in text.lower():
                return "Footwear"
            return "Leather Shoes"
        elif source_lang == "en" and target_lang == "hi":
            return f"[HI] {text}"
        return text

    mock_translate.side_effect = side_effect_translate

    payload = {
        "category": "जूते",
        "description": "चमड़े के जूते",
        "manufacturer_scale": "msme",
        "is_imported": False,
        "lang": {"lang_code": "hi"}
    }
    response = client.post("/compliance/check", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()

    assert data["response_lang"] == "hi"
    assert data["translation_unavailable"] is False

    assert "[HI]" in data["qco_result"]["reasoning"]
    for req in data["requirements"]:
        assert "[HI]" in req["requirement"]

    assert data["qco_result"]["qco_id"] == "QCO-FOOTWEAR-2024"
    assert data["qco_result"]["standard_id"] == "IS 17043:2018"
    assert data["qco_result"]["effective_date"] == "2024-08-01"
    assert data["qco_result"]["source"]["document_id"] == "QCO-FOOTWEAR-2024"
    assert data["qco_result"]["source"]["clause"] == "Paragraph 2"

@patch("app.routers.compliance.translate_text", new_callable=AsyncMock)
def test_compliance_check_fallback_behavior(mock_translate):
    mock_translate.side_effect = BhashiniUnavailableError("Connection refused")

    payload = {
        "category": "Footwear",
        "description": "Leather boots",
        "manufacturer_scale": "msme",
        "is_imported": False,
        "lang": {"lang_code": "hi"}
    }
    response = client.post("/compliance/check", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()

    assert data["translation_unavailable"] is True
    assert data["response_lang"] == "en"
    assert data["qco_result"]["qco_id"] == "QCO-FOOTWEAR-2024"

@patch("app.routers.voice.synthesize_speech", new_callable=AsyncMock)
@patch("app.routers.voice.transcribe", new_callable=AsyncMock)
def test_voice_websocket_stream_roundtrip(mock_transcribe, mock_tts):
    mock_transcribe.return_value = "क्या खिलौनों पर QCO लागू होता है?"
    mock_tts.return_value = b"FAKE_AUDIO_BYTES"

    with client.websocket_connect("/voice/stream?X-API-Key=demo-key-123", headers=AUTH_HEADERS) as websocket:
        websocket.send_json({"type": "config", "lang_code": "hi"})
        ack = websocket.receive_json()
        assert ack["type"] == "config_ack"

        websocket.send_bytes(b"DUMMY_AUDIO_STREAM_DATA")
        websocket.send_json({"type": "audio_end"})

        msg_transcript = websocket.receive_json()
        assert msg_transcript["type"] == "transcript"
        assert msg_transcript["text"] == "क्या खिलौनों पर QCO लागू होता है?"

        msg_response = websocket.receive_json()
        assert msg_response["type"] == "response"
        assert "query_response" in msg_response
        assert msg_response["audio_b64"] != ""


def test_voice_websocket_rejects_missing_key():
    import pytest as _pytest
    from fastapi.testclient import TestClient as _TC
    from starlette.websockets import WebSocketDisconnect as _WSD
    from app.main import app as _app
    with _pytest.raises(_WSD):
        with _TC(_app).websocket_connect("/voice/stream"):
            pass