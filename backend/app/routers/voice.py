import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.schemas.language import LanguagePreference
from app.schemas.compliance import QueryInput
from app.routers.query import handle_query
from app.services.translation import (
    transcribe,
    synthesize_speech,
    BhashiniUnavailableError,
)

logger = logging.getLogger("voice_stream")
router = APIRouter(prefix="/voice", tags=["voice"])

@router.websocket("/stream")
async def voice_stream_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket voice stream connection established.")

    lang_code = "hi"  # Default source language for voice
    audio_buffer = bytearray()

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                # Append raw binary audio chunk
                audio_buffer.extend(message["bytes"])

            elif "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                except Exception:
                    data = {}

                msg_type = data.get("type", "")

                if msg_type == "config":
                    lang_code = data.get("lang_code", lang_code)
                    await websocket.send_json({"type": "config_ack", "lang_code": lang_code})

                elif msg_type == "audio_chunk":
                    # Base64 audio chunk in JSON
                    import base64
                    chunk_b64 = data.get("audio_b64", "")
                    if chunk_b64:
                        audio_buffer.extend(base64.b64decode(chunk_b64))

                elif msg_type in ["audio_end", "process"]:
                    if not audio_buffer:
                        await websocket.send_json({"type": "error", "message": "No audio received."})
                        continue

                    raw_audio = bytes(audio_buffer)
                    audio_buffer.clear()

                    # 1. Transcribe audio to text
                    transcript = ""
                    translation_unavailable = False
                    try:
                        transcript = await transcribe(raw_audio, source_lang=lang_code)
                    except BhashiniUnavailableError as err:
                        logger.warning(f"Voice ASR unavailable: {err}")
                        transcript = "Voice input (transcription unavailable)"
                        translation_unavailable = True

                    # 2. Send transcript back immediately for low perceived latency
                    await websocket.send_json({
                        "type": "transcript",
                        "text": transcript,
                        "lang_code": lang_code,
                        "translation_unavailable": translation_unavailable
                    })

                    # 3. Process query through backend pipeline
                    query_input = QueryInput(
                        query=transcript,
                        lang=LanguagePreference(lang_code=lang_code)
                    )
                    query_res = await handle_query(query_input)

                    # 4. Synthesize speech for output text
                    audio_b64 = ""
                    try:
                        tts_bytes = await synthesize_speech(query_res.message, target_lang=lang_code)
                        if tts_bytes:
                            import base64
                            audio_b64 = base64.b64encode(tts_bytes).decode("utf-8")
                    except BhashiniUnavailableError as err:
                        logger.warning(f"Voice TTS unavailable: {err}")

                    # 5. Send response JSON + TTS audio
                    await websocket.send_json({
                        "type": "response",
                        "query_response": query_res.model_dump(),
                        "audio_b64": audio_b64
                    })

    except WebSocketDisconnect:
        logger.info("WebSocket voice stream client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
        except Exception:
            pass
