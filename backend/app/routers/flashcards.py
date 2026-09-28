"""
Flashcard router.
POST /flashcards/generate — generate BIS standards flashcards via LLM
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.flashcard_service import generate_flashcards
from app.services.rag_service import RAGService
from app.services.cache_service import make_cache_key, get_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/flashcards", tags=["flashcards"])


class FlashcardRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500, description="BIS topic for flashcard generation")
    num_cards: int = Field(10, ge=1, le=20, description="Number of flashcards to generate")
    use_rag: bool = Field(True, description="Retrieve BIS context from vector store to ground flashcards")


class Flashcard(BaseModel):
    question: str
    answer: str


class FlashcardResponse(BaseModel):
    topic: str
    num_requested: int
    num_generated: int
    rag_used: bool
    flashcards: list[Flashcard]


@router.post("/generate", response_model=FlashcardResponse)
async def generate_flashcard_set(body: FlashcardRequest):
    """Generate BIS standards educational flashcards for a given topic."""
    # Check cache first
    cache_key = make_cache_key(body.topic, body.num_cards, body.use_rag, prefix="flashcards")
    cached = get_cache().get(cache_key)
    if cached:
        logger.debug(f"Flashcard cache HIT: {cache_key}")
        return FlashcardResponse(**cached)

    # Optionally retrieve RAG context
    context = ""
    rag_used = False
    if body.use_rag and RAGService.is_available():
        chunks = RAGService.retrieve_texts(body.topic, k=4)
        if chunks:
            context = "\n\n".join(chunks)
            rag_used = True

    # Generate flashcards via LLM
    cards = await generate_flashcards(body.topic, context=context, num_cards=body.num_cards)

    result = FlashcardResponse(
        topic=body.topic,
        num_requested=body.num_cards,
        num_generated=len(cards),
        rag_used=rag_used,
        flashcards=[Flashcard(**c) for c in cards],
    )

    # Cache for 10 minutes
    get_cache().set(cache_key, result.model_dump(), ttl=600)
    return result
