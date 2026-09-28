import base64
import logging
import httpx
from typing import Any
from app.core.config import settings
from app.schemas.language import SupportedLanguage

logger = logging.getLogger("bhashini_translation")

class BhashiniUnavailableError(Exception):
    """Raised when Bhashini service is unreachable or credentials/API calls fail."""
    pass

SUPPORTED_LANGUAGES_LIST = [
    SupportedLanguage(code="en", name="English", native_name="English"),
    SupportedLanguage(code="hi", name="Hindi", native_name="हिन्दी"),
    SupportedLanguage(code="ta", name="Tamil", native_name="தமிழ்"),
    SupportedLanguage(code="te", name="Telugu", native_name="తెలుగు"),
    SupportedLanguage(code="bn", name="Bengali", native_name="বাংলা"),
    SupportedLanguage(code="mr", name="Marathi", native_name="मराठी"),
    SupportedLanguage(code="gu", name="Gujarati", native_name="ગુજરાતી"),
    SupportedLanguage(code="kn", name="Kannada", native_name="கன்னட"),
    SupportedLanguage(code="ml", name="Malayalam", native_name="മലയാളം"),
    SupportedLanguage(code="pa", name="Punjabi", native_name="ਪੰਜਾਬੀ"),
    SupportedLanguage(code="or", name="Odia", native_name="ଓଡ଼ିଆ"),
    SupportedLanguage(code="as", name="Assamese", native_name="অসমীয়া"),
]

# Cache pipeline config per task/language pair
_pipeline_config_cache: dict[str, Any] = {}

def get_supported_languages() -> list[SupportedLanguage]:
    """Return static/cached list of supported Bhashini languages."""
    return SUPPORTED_LANGUAGES_LIST

async def get_pipeline_config(
    source_lang: str,
    target_lang: str | None = None,
    task_types: list[str] | None = None
) -> dict[str, Any]:
    """
    Fetches compute pipeline config & authorization keys from Bhashini ULCA API.
    Refreshes token and service endpoints.
    """
    user_id = settings.BHASHINI_USER_ID
    api_key = settings.BHASHINI_API_KEY
    pipeline_id = settings.BHASHINI_PIPELINE_ID

    if not user_id or not api_key:
        raise BhashiniUnavailableError("Bhashini credentials (BHASHINI_USER_ID, BHASHINI_API_KEY) are not configured.")

    if task_types is None:
        task_types = ["translation"]

    cache_key = f"{source_lang}_{target_lang}_{','.join(task_types)}"
    if cache_key in _pipeline_config_cache:
        return _pipeline_config_cache[cache_key]

    tasks_payload = []
    for tt in task_types:
        task_cfg: dict[str, Any] = {"taskType": tt}
        lang_config: dict[str, Any] = {"sourceLanguage": source_lang}
        if target_lang and tt in ["translation", "tts"]:
            lang_config["targetLanguage"] = target_lang
        task_cfg["config"] = {"language": lang_config}
        tasks_payload.append(task_cfg)

    payload = {
        "pipelineTasks": tasks_payload,
        "pipelineRequestConfig": {
            "pipelineId": pipeline_id
        }
    }

    headers = {
        "userID": user_id,
        "ulcaApiKey": api_key,
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(settings.BHASHINI_PIPELINE_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                raise BhashiniUnavailableError(f"Bhashini pipeline config call failed HTTP {resp.status_code}: {resp.text}")
            data = resp.json()
            _pipeline_config_cache[cache_key] = data
            return data
    except Exception as e:
        logger.warning(f"Bhashini pipeline config error: {e}")
        raise BhashiniUnavailableError(f"Bhashini unreachable: {str(e)}") from e

async def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """
    Translates text between source_lang and target_lang via Bhashini NMT API.
    Raises BhashiniUnavailableError on failure.
    """
    if source_lang == target_lang or not text.strip():
        return text

    config_data = await get_pipeline_config(source_lang=source_lang, target_lang=target_lang, task_types=["translation"])

    try:
        pipeline_resp = config_data.get("pipelineResponseConfig", [])
        if not pipeline_resp:
            raise BhashiniUnavailableError("Invalid pipeline configuration response from Bhashini.")

        nmt_service = next((task for task in pipeline_resp if task.get("taskType") == "translation"), None)
        if not nmt_service:
            raise BhashiniUnavailableError("No translation task found in Bhashini response config.")

        callback_url = config_data.get("pipelineInferenceAPIEndPoint", {}).get("callbackUrl")
        inference_key_name = config_data.get("pipelineInferenceAPIEndPoint", {}).get("inferenceApiKey", {}).get("name", "Authorization")
        inference_key_val = config_data.get("pipelineInferenceAPIEndPoint", {}).get("inferenceApiKey", {}).get("value", "")

        if not callback_url:
            raise BhashiniUnavailableError("Bhashini callback endpoint URL missing.")

        compute_payload = {
            "pipelineTasks": [
                {
                    "taskType": "translation",
                    "config": {
                        "language": {
                            "sourceLanguage": source_lang,
                            "targetLanguage": target_lang
                        },
                        "serviceId": nmt_service.get("config", [{}])[0].get("serviceId")
                    }
                }
            ],
            "inputData": {
                "input": [
                    {"source": text}
                ]
            }
        }

        headers = {
            inference_key_name: inference_key_val,
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(callback_url, json=compute_payload, headers=headers)
            if res.status_code != 200:
                raise BhashiniUnavailableError(f"Bhashini translation compute failed HTTP {res.status_code}: {res.text}")

            result_json = res.json()
            translated = (
                result_json.get("pipelineResponse", [{}])[0]
                .get("output", [{}])[0]
                .get("target")
            )
            if not translated:
                raise BhashiniUnavailableError("Empty target text in Bhashini translation response.")
            return translated
    except Exception as e:
        if isinstance(e, BhashiniUnavailableError):
            raise e
        raise BhashiniUnavailableError(f"Bhashini NMT error: {str(e)}") from e

async def transcribe(audio_bytes: bytes, source_lang: str) -> str:
    """
    Transcribes audio bytes to text via Bhashini ASR API.
    Raises BhashiniUnavailableError on failure.
    """
    config_data = await get_pipeline_config(source_lang=source_lang, task_types=["asr"])

    try:
        pipeline_resp = config_data.get("pipelineResponseConfig", [])
        asr_service = next((task for task in pipeline_resp if task.get("taskType") == "asr"), None)
        if not asr_service:
            raise BhashiniUnavailableError("No ASR task found in Bhashini response config.")

        callback_url = config_data.get("pipelineInferenceAPIEndPoint", {}).get("callbackUrl")
        inference_key_name = config_data.get("pipelineInferenceAPIEndPoint", {}).get("inferenceApiKey", {}).get("name", "Authorization")
        inference_key_val = config_data.get("pipelineInferenceAPIEndPoint", {}).get("inferenceApiKey", {}).get("value", "")

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        compute_payload = {
            "pipelineTasks": [
                {
                    "taskType": "asr",
                    "config": {
                        "language": {"sourceLanguage": source_lang},
                        "serviceId": asr_service.get("config", [{}])[0].get("serviceId"),
                        "audioFormat": "wav",
                        "samplingRate": 16000
                    }
                }
            ],
            "inputData": {
                "audio": [
                    {"audioContent": audio_b64}
                ]
            }
        }

        headers = {
            inference_key_name: inference_key_val,
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(callback_url, json=compute_payload, headers=headers)
            if res.status_code != 200:
                raise BhashiniUnavailableError(f"Bhashini ASR compute failed HTTP {res.status_code}: {res.text}")

            result_json = res.json()
            transcript = (
                result_json.get("pipelineResponse", [{}])[0]
                .get("output", [{}])[0]
                .get("source")
            )
            if transcript is None:
                raise BhashiniUnavailableError("Empty transcript in Bhashini ASR response.")
            return transcript
    except Exception as e:
        if isinstance(e, BhashiniUnavailableError):
            raise e
        raise BhashiniUnavailableError(f"Bhashini ASR error: {str(e)}") from e

async def synthesize_speech(text: str, target_lang: str) -> bytes:
    """
    Synthesizes text into speech audio bytes via Bhashini TTS API.
    Raises BhashiniUnavailableError on failure.
    """
    if not text.strip():
        return b""

    config_data = await get_pipeline_config(source_lang=target_lang, target_lang=target_lang, task_types=["tts"])

    try:
        pipeline_resp = config_data.get("pipelineResponseConfig", [])
        tts_service = next((task for task in pipeline_resp if task.get("taskType") == "tts"), None)
        if not tts_service:
            raise BhashiniUnavailableError("No TTS task found in Bhashini response config.")

        callback_url = config_data.get("pipelineInferenceAPIEndPoint", {}).get("callbackUrl")
        inference_key_name = config_data.get("pipelineInferenceAPIEndPoint", {}).get("inferenceApiKey", {}).get("name", "Authorization")
        inference_key_val = config_data.get("pipelineInferenceAPIEndPoint", {}).get("inferenceApiKey", {}).get("value", "")

        compute_payload = {
            "pipelineTasks": [
                {
                    "taskType": "tts",
                    "config": {
                        "language": {"sourceLanguage": target_lang},
                        "serviceId": tts_service.get("config", [{}])[0].get("serviceId"),
                        "gender": "female"
                    }
                }
            ],
            "inputData": {
                "input": [
                    {"source": text}
                ]
            }
        }

        headers = {
            inference_key_name: inference_key_val,
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(callback_url, json=compute_payload, headers=headers)
            if res.status_code != 200:
                raise BhashiniUnavailableError(f"Bhashini TTS compute failed HTTP {res.status_code}: {res.text}")

            result_json = res.json()
            audio_b64 = (
                result_json.get("pipelineResponse", [{}])[0]
                .get("audio", [{}])[0]
                .get("audioContent")
            )
            if not audio_b64:
                raise BhashiniUnavailableError("Empty audio content in Bhashini TTS response.")
            return base64.b64decode(audio_b64)
    except Exception as e:
        if isinstance(e, BhashiniUnavailableError):
            raise e
        raise BhashiniUnavailableError(f"Bhashini TTS error: {str(e)}") from e
