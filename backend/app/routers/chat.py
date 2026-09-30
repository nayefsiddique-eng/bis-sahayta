"""
POST /chat — main conversational interface with session memory.
Integrates: intent classifier → RAG → LLM → session history.
Frontend-attachable friendly: supports both {message} and {query} payloads,
and returns both {reply, sources} and {answer, citations} schema formats.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.services.intent_classifier import classify_intent
from app.services.rag_service import RAGService
from app.core.config import settings
from app.services.llm_service import LLMService, get_llm_router
from app.services.session_db import (
    create_session,
    get_session,
    delete_session,
    add_message,
    get_history,
    get_history_as_pairs,
    update_session_context,
    list_sessions,
    get_first_user_message,
)
from app.services.translation import translate_text, BhashiniUnavailableError
from app.services.cache_service import get_cache, make_cache_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: Optional[str] = Field(None, min_length=1, max_length=4000)
    query: Optional[str] = Field(None, min_length=1, max_length=4000, description="Alias for message")
    session_id: Optional[str] = Field(None, description="Existing session ID. Omit to start a new session.")
    lang: str = Field("en", description="Language code (e.g. 'en', 'hi')")
    use_rag: bool = Field(True, description="Whether to retrieve context from the document store.")
    n_results: Optional[int] = Field(5, description="Number of RAG results")
    style: Optional[Literal["simple", "short", "technical"]] = Field("simple", description="Response style mode")
    document_id: Optional[str] = Field(None, description="Optional uploaded document ID to focus analysis/RAG on")
    model: Optional[Literal["auto", "gemini", "gemma4", "qwen"]] = Field(
        "auto", description="LLM model to use. 'auto' tries Gemini first then falls back."
    )

    @model_validator(mode="before")
    @classmethod
    def resolve_message_query(cls, data: dict):
        if isinstance(data, dict):
            msg = data.get("message") or data.get("query")
            if not msg:
                raise ValueError("Either 'message' or 'query' must be provided.")
            data["message"] = msg
            data["query"] = msg
        return data


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    answer: str  # Frontend alias for reply
    intent: str
    rag_used: bool
    relevance: Optional[float] = Field(None, description="Top RAG cosine similarity score (0.0 to 1.0) or null")
    sources: list[dict] = []
    citations: list[dict] = []  # Frontend alias for sources
    translation_unavailable: bool = False
    response_lang: str = "en"
    model_used: str = "gemini"
    fallback_used: bool = False
    fallback_reason: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: dict):
        if isinstance(data, dict):
            if "reply" in data and "answer" not in data:
                data["answer"] = data["reply"]
            elif "answer" in data and "reply" not in data:
                data["reply"] = data["answer"]

            if "sources" in data and "citations" not in data:
                data["citations"] = data["sources"]
            elif "citations" in data and "sources" not in data:
                data["sources"] = data["citations"]

            if "confidence" in data and "relevance" not in data:
                data["relevance"] = data["confidence"]
        return data


# ---------------------------------------------------------------------------
# Sessions sub-router
# ---------------------------------------------------------------------------

sessions_router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionCreateRequest(BaseModel):
    context: Optional[dict] = None


@sessions_router.post("", status_code=201)
def create_new_session(body: SessionCreateRequest = None):
    payload = body or SessionCreateRequest()
    session = create_session(context=payload.context)
    return session


@sessions_router.get("")
def get_all_sessions(limit: int = 50):
    """List recent chat sessions (newest first: id, preview, updated_at)."""
    sessions = list_sessions(limit=limit)
    res = []
    for s in sessions:
        sid = s["session_id"]
        first_msg = get_first_user_message(sid)
        preview = first_msg if first_msg else "New Chat"
        res.append({
            "id": sid,
            "session_id": sid,
            "preview": preview,
            "updated_at": s["updated_at"],
            "created_at": s["created_at"],
        })
    return res


@sessions_router.get("/{session_id}")
def get_session_info(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return session


@sessions_router.get("/{session_id}/messages")
def get_session_messages(session_id: str):
    """Retrieve full message history for a session (used by frontend web chat UIs)."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return get_history(session_id, limit=100)


@sessions_router.delete("/{session_id}")
def delete_existing_session(session_id: str):
    """Delete session and clear history."""
    success = delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {"status": "success", "message": f"Session '{session_id}' deleted."}


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------

@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest):
    # 1. Resolve or create session
    session_id = body.session_id
    if session_id:
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    else:
        session = create_session()
        session_id = session["session_id"]

    prompt_text = body.message or body.query or ""

    # 2. Translate to English if needed
    message_en = prompt_text
    translation_unavailable = False
    if body.lang and body.lang != "en":
        try:
            message_en = await translate_text(prompt_text, source_lang=body.lang, target_lang="en")
        except BhashiniUnavailableError:
            translation_unavailable = True

    # 3. Classify intent
    intent = classify_intent(message_en)

    # 4. Retrieve RAG context & uploaded document context
    rag_chunks: list[dict] = []
    rag_texts: list[str] = []
    rag_used = False
    confidence: Optional[float] = None

    # Handle attached document text if document_id is provided
    if body.document_id:
        from app.routers.documents import _load_meta_db
        db = _load_meta_db()
        doc_meta = db.get(body.document_id)
        if doc_meta:
            text_path = Path(doc_meta.get("text_path", ""))
            doc_text = ""
            if text_path.exists():
                doc_text = text_path.read_text(encoding="utf-8")
            elif doc_meta.get("extracted_text_preview"):
                doc_text = doc_meta["extracted_text_preview"]

            if doc_text:
                fname = doc_meta.get("filename", "Uploaded Document")
                rag_texts.append(f"[Uploaded Document: {fname} (ID: {body.document_id})]:\n{doc_text[:3000]}")
                rag_used = True
                formatted_doc_source = {
                    "title": f"Attached Document: {fname}",
                    "document_id": body.document_id,
                    "clause": "Full Text",
                    "url": "",
                    "snippet": doc_text[:300],
                    "score": 1.0,
                }

    if body.use_rag and RAGService.is_available():
        top_k = body.n_results or 5
        vector_chunks = RAGService.retrieve_with_metadata(message_en, k=top_k)
        vector_chunks = [_c for _c in vector_chunks if float(_c.get("score") or 0) >= settings.RAG_MIN_SCORE]
        # Deduplicate by text content (remove near-identical chunks)
        seen_texts: set = set()
        deduped_chunks = []
        for _c in vector_chunks:
            _text_key = _c.get("text", "")[:100]
            if _text_key not in seen_texts:
                seen_texts.add(_text_key)
                deduped_chunks.append(_c)
        rag_chunks = deduped_chunks
        # Build readable RAG context for the LLM prompt
        for c in rag_chunks:
            meta = c.get("metadata") or {}
            std_id = meta.get("standard_id") or meta.get("is_number") or meta.get("title") or "BIS document"
            page = meta.get("page_number") or meta.get("page") or "?"
            idx = len(rag_texts) + 1
            rag_texts.append(f"[{idx}] {std_id}, page {page}: {c['text']}")
        rag_used = bool(rag_texts)
        if rag_chunks:
            top_score = rag_chunks[0].get("score")
            if top_score is not None:
                confidence = round(float(top_score), 4)

    # Consistent sources schema (title, document_id, clause, url, snippet)
    formatted_sources = []
    if 'formatted_doc_source' in locals() and formatted_doc_source:
        formatted_sources.append(formatted_doc_source)

    for chunk in rag_chunks:
        meta = chunk.get("metadata", {})
        title = (
            meta.get("title")
            or meta.get("standard_id")
            or meta.get("is_number")
            or meta.get("document_id")
            or "BIS Standard"
        )
        doc_id = (
            meta.get("document_id")
            or meta.get("standard_id")
            or meta.get("is_number")
            or "IS-STD"
        )
        clause = str(meta.get("clause") or meta.get("page_number") or meta.get("page") or "")
        url = meta.get("url") or ""
        snippet = chunk.get("text", "")[:300]
        score = chunk.get("score")

        formatted_sources.append({
            "title": title,
            "document_id": doc_id,
            "clause": clause,
            "url": url,
            "snippet": snippet,
            "score": score,
        })

    # 5. Load conversation history
    history = get_history_as_pairs(session_id, n_turns=6)
    session_context_str = ""
    if session and session.get("context"):
        ctx = session["context"]
        parts = [f"{k}: {v}" for k, v in ctx.items() if v]
        session_context_str = "; ".join(parts)

    # 6. Check response cache
    reply_en = None
    _rag_fp = hashlib.sha1("".join(rag_texts).encode("utf-8")).hexdigest()[:12]
    cache_key = make_cache_key(f"{message_en}_{body.style}_{_rag_fp}", intent.value, prefix="chat")
    if not history and not session_context_str:
        cached = get_cache().get(cache_key)
        if cached:
            logger.debug(f"Chat cache HIT: {cache_key}")
            reply_en = cached

    # 7. LLM completion via router (supports Gemini → Gemma4 → Qwen fallback)
    model_used = "mock"
    fallback_used = False
    fallback_reason: Optional[str] = None

    if reply_en is None:
        prompt = LLMService.build_chat_prompt(
            question=message_en,
            context_chunks=rag_texts,
            history=history,
            session_context=session_context_str,
            style=body.style or "simple",
        )
        router_result = await get_llm_router().generate(
            prompt,
            model=body.model or "auto",
            max_tokens=1024,
        )
        reply_en = router_result["text"]
        model_used = router_result["model_used"]
        fallback_used = router_result["fallback_used"]
        fallback_reason = router_result["fallback_reason"]

        if not history and not session_context_str:
            get_cache().set(cache_key, reply_en, ttl=300)
    else:
        # Cache hit — attribute to configured provider name
        model_used = settings.LLM_DEFAULT_MODEL or "gemini"

    # 8. Translate reply back if needed
    reply_final = reply_en
    response_lang = "en"
    if body.lang and body.lang != "en" and not translation_unavailable:
        try:
            reply_final = await translate_text(reply_en, source_lang="en", target_lang=body.lang)
            response_lang = body.lang
        except BhashiniUnavailableError:
            translation_unavailable = True

    # 9. Persist conversation turn
    add_message(session_id, "user", prompt_text)
    add_message(session_id, "assistant", reply_final, metadata={"sources": formatted_sources, "confidence": confidence})

    # 10. Update session context
    ctx = (session.get("context") or {}) if session else {}
    ctx["last_intent"] = intent.value
    update_session_context(session_id, ctx)

    return ChatResponse(
        session_id=session_id,
        reply=reply_final,
        answer=reply_final,
        intent=intent.value,
        rag_used=rag_used,
        relevance=confidence,
        sources=formatted_sources,
        citations=formatted_sources,
        translation_unavailable=translation_unavailable,
        response_lang=response_lang,
        model_used=model_used,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
    )
