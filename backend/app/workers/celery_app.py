"""
Celery application and task definitions.
Workers process: document indexing, batch compliance checks, async OCR.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from celery import Celery  # type: ignore
    from app.core.config import settings

    celery_app = Celery(
        "bis_tasks",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
    CELERY_AVAILABLE = True
    logger.info("Celery app initialized.")
except ImportError:
    celery_app = None  # type: ignore
    CELERY_AVAILABLE = False
    logger.warning("Celery not installed. Async task processing unavailable.")


# ---------------------------------------------------------------------------
# Task definitions (only registered if Celery is available)
# ---------------------------------------------------------------------------

if CELERY_AVAILABLE and celery_app:

    @celery_app.task(name="tasks.process_document", bind=True, max_retries=3)
    def process_document_task(self, document_id: str, file_path: str, content_type: str):
        """
        Async document processing: OCR + metadata extraction.
        Called after document upload to run heavy processing in background.
        """
        import asyncio
        from pathlib import Path

        logger.info(f"[Task] Processing document: {document_id}")
        try:
            data = Path(file_path).read_bytes()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            from app.services.ocr_service import OCRService
            text = loop.run_until_complete(
                OCRService.extract_text(data, mime_type=content_type)
            )
            loop.close()
            logger.info(f"[Task] Document {document_id} processed: {len(text)} chars")
            return {"document_id": document_id, "status": "done", "char_count": len(text)}
        except Exception as exc:
            logger.error(f"[Task] process_document failed: {exc}")
            raise self.retry(exc=exc, countdown=30)

    @celery_app.task(name="tasks.batch_compliance_check", bind=True, max_retries=2)
    def batch_compliance_check_task(self, products: list):
        """
        Run compliance checks for a batch of products asynchronously.
        Each product is a dict matching the ProductInput schema.
        """
        logger.info(f"[Task] Batch compliance check for {len(products)} products")
        results = []
        from app.services.compliance_engine import check_qco_applicability, resolve_requirements
        from app.schemas.product import ProductInput
        from app.schemas.language import LanguagePreference

        for p_data in products:
            try:
                product = ProductInput(
                    category=p_data.get("category", ""),
                    description=p_data.get("description", ""),
                    manufacturer_scale=p_data.get("manufacturer_scale", "large"),
                    is_imported=p_data.get("is_imported", False),
                    lang=LanguagePreference(lang_code="en"),
                )
                primary, _, _ = check_qco_applicability(product)
                results.append({
                    "category": p_data.get("category"),
                    "applies": primary.applies,
                    "qco_id": primary.qco_id,
                })
            except Exception as exc:
                results.append({"category": p_data.get("category"), "error": str(exc)})

        return {"status": "done", "total": len(products), "results": results}

    @celery_app.task(name="tasks.generate_flashcards_async", bind=True, max_retries=2)
    def generate_flashcards_async_task(self, topic: str, num_cards: int = 10):
        """Async flashcard generation via LLM."""
        import asyncio
        logger.info(f"[Task] Generating {num_cards} flashcards for: {topic!r}")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            from app.services.flashcard_service import generate_flashcards
            cards = loop.run_until_complete(generate_flashcards(topic, num_cards=num_cards))
            loop.close()
            return {"status": "done", "topic": topic, "flashcards": cards}
        except Exception as exc:
            raise self.retry(exc=exc, countdown=60)
