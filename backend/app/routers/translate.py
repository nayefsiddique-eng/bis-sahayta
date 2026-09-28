from fastapi import APIRouter
from app.schemas.language import (
    TranslateTextRequest,
    TranslateTextResponse,
    LanguageSupportResponse,
)
from app.services.translation import (
    translate_text,
    get_supported_languages,
    BhashiniUnavailableError,
)

router = APIRouter(prefix="", tags=["translation"])


@router.get("/languages/supported", response_model=LanguageSupportResponse)
def list_supported_languages():
    langs = get_supported_languages()
    return LanguageSupportResponse(languages=langs)


async def _do_translate(payload: TranslateTextRequest) -> TranslateTextResponse:
    """Shared translation handler used by both /translate and /translate/text."""
    try:
        translated = await translate_text(
            text=payload.text,
            source_lang=payload.source_lang,
            target_lang=payload.target_lang,
        )
        return TranslateTextResponse(
            translated_text=translated,
            source_lang=payload.source_lang,
            target_lang=payload.target_lang,
            translation_unavailable=False,
        )
    except BhashiniUnavailableError:
        # Graceful degradation — return original text, flag unavailable
        return TranslateTextResponse(
            translated_text=payload.text,
            source_lang=payload.source_lang,
            target_lang=payload.target_lang,
            translation_unavailable=True,
        )


@router.post("/translate", response_model=TranslateTextResponse)
async def translate_endpoint(payload: TranslateTextRequest):
    """Translate text via Bhashini. Primary endpoint: POST /translate"""
    return await _do_translate(payload)


@router.post("/translate/text", response_model=TranslateTextResponse)
async def translate_text_endpoint(payload: TranslateTextRequest):
    """Translate text via Bhashini. Alias endpoint: POST /translate/text"""
    return await _do_translate(payload)

