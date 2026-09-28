"""
Flashcard generation service.
Generates BIS standards flashcards using the LLM service (with MockProvider fallback).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from app.services.llm_service import LLMService, LLMProvider

logger = logging.getLogger(__name__)

FLASHCARD_SYSTEM_PROMPT = """You are an expert in BIS (Bureau of Indian Standards) compliance and Indian standards.
Generate educational flashcards from the provided content.
Each flashcard must have a clear QUESTION and a concise, accurate ANSWER grounded in BIS standards.
Do NOT fabricate standards, regulation numbers, or compliance requirements.
If the topic is unclear, generate general BIS knowledge flashcards."""


def _parse_flashcards(raw: str) -> list[dict]:
    """Parse LLM output into structured flashcard list."""
    cards = []
    # Try to split by numbered items or Q:/A: patterns
    blocks = re.split(r"\n(?=\d+[\.\)]|\bQ[\.\:]|\bQuestion[\.\:])", raw.strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Extract Q and A
        q_match = re.search(r"(?:Q[\.\:]|Question[\.\:]|^\d+[\.\)])\s*(.+?)(?:\n|$)", block, re.IGNORECASE | re.MULTILINE)
        a_match = re.search(r"(?:A[\.\:]|Answer[\.\:])\s*(.+)", block, re.IGNORECASE | re.DOTALL)

        if q_match and a_match:
            question = q_match.group(1).strip()
            answer = a_match.group(1).strip()
            if question and answer:
                cards.append({"question": question, "answer": answer})

    # Fallback: split into pairs if structured parsing failed
    if not cards and raw:
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        for i in range(0, len(lines) - 1, 2):
            cards.append({"question": lines[i], "answer": lines[i + 1]})

    return cards[:20]  # Cap at 20 flashcards


async def generate_flashcards(
    topic: str,
    context: str = "",
    num_cards: int = 10,
    provider: Optional[LLMProvider] = None,
) -> list[dict]:
    """
    Generate flashcards for a given BIS topic.

    Args:
        topic: The BIS topic (e.g., "IS 1234:2021 Cement Standards").
        context: Optional additional context (e.g., retrieved RAG chunks).
        num_cards: Number of flashcards to generate (1–20).
        provider: Override LLM provider (for testing).

    Returns:
        List of dicts with 'question' and 'answer' keys.
    """
    num_cards = max(1, min(num_cards, 20))
    ctx_section = f"\n\nCONTEXT:\n{context[:2000]}" if context else ""

    prompt = (
        f"Generate exactly {num_cards} educational flashcards about the following BIS topic:\n\n"
        f"TOPIC: {topic}{ctx_section}\n\n"
        f"Format each flashcard exactly as:\n"
        f"Q: [question]\nA: [answer]\n\n"
        f"Flashcards:"
    )

    try:
        raw = await LLMService.complete(
            prompt,
            system=FLASHCARD_SYSTEM_PROMPT,
            max_tokens=1500,
            provider=provider,
        )
        cards = _parse_flashcards(raw)
        if not cards:
            # Return a well-formed stub so the endpoint never returns empty
            cards = [
                {
                    "question": f"What is the key requirement of {topic}?",
                    "answer": "Configure LLM_PROVIDER=gemini with GEMINI_API_KEY for real content.",
                }
            ]
        logger.info(f"Generated {len(cards)} flashcards for topic: {topic!r}")
        return cards
    except Exception as exc:
        logger.error(f"Flashcard generation error: {exc}")
        return [
            {
                "question": f"What is {topic}?",
                "answer": f"Flashcard generation failed: {str(exc)[:200]}",
            }
        ]
