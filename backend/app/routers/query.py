from fastapi import APIRouter
from app.schemas.compliance import QueryInput, QueryResponse
from app.services.intent_classifier import classify_intent
from app.services.translation import translate_text, BhashiniUnavailableError

router = APIRouter()

@router.post("/query", response_model=QueryResponse)
async def handle_query(input_data: QueryInput):
    target_lang = input_data.lang.lang_code
    query_text = input_data.query
    translation_unavailable = False

    if target_lang != "en":
        try:
            query_text = await translate_text(
                text=input_data.query,
                source_lang=target_lang,
                target_lang="en"
            )
        except BhashiniUnavailableError:
            translation_unavailable = True

    intent = classify_intent(query_text)

    intent_messages = {
        "general_qa": "General BIS standards query identified.",
        "compliance_check": "Product compliance evaluation query identified.",
        "certification_process": "Certification roadmap & process query identified.",
        "hybrid": "Multi-topic query requiring compliance and process evaluation identified."
    }

    message_en = intent_messages.get(intent.value, "Query classified successfully.")
    final_message = message_en

    if target_lang != "en" and not translation_unavailable:
        try:
            final_message = await translate_text(
                text=message_en,
                source_lang="en",
                target_lang=target_lang
            )
        except BhashiniUnavailableError:
            translation_unavailable = True
            final_message = message_en

    return QueryResponse(
        intent=intent.value,
        message=final_message,
        data={
            "original_query": input_data.query,
            "processed_query_en": query_text,
            "detected_intent": intent.value
        },
        response_lang=target_lang if not translation_unavailable else "en",
        translation_unavailable=translation_unavailable
    )
