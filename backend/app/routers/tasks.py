"""
Tasks router — async job submission and status polling.
POST /tasks  — submit a background task (document processing, batch compliance, flashcards)
GET  /tasks/{task_id} — get task status and result
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TaskSubmitRequest(BaseModel):
    task_type: str = Field(
        ...,
        description="One of: batch_compliance_check | generate_flashcards | process_document",
    )
    payload: dict = Field(default_factory=dict, description="Task-specific payload")


class TaskStatusResponse(BaseModel):
    task_id: str
    task_type: str
    status: str  # pending | started | success | failure | retry
    result: Optional[Any] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# In-memory task registry (fallback when Celery/Redis unavailable)
# ---------------------------------------------------------------------------

_task_registry: dict[str, dict] = {}


def _submit_in_memory(task_type: str, payload: dict) -> str:
    """Synchronous in-memory fallback when Celery is unavailable."""
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    _task_registry[task_id] = {"task_id": task_id, "task_type": task_type, "status": "pending"}

    result = None
    error = None
    try:
        if task_type == "batch_compliance_check":
            from app.services.compliance_engine import check_qco_applicability
            from app.schemas.product import ProductInput
            from app.schemas.language import LanguagePreference

            products = payload.get("products", [])
            results = []
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
                    results.append({"category": p_data.get("category"), "applies": primary.applies, "qco_id": primary.qco_id})
                except Exception as exc:
                    results.append({"category": p_data.get("category"), "error": str(exc)})
            result = {"total": len(products), "results": results}

        elif task_type == "generate_flashcards":
            import asyncio
            from app.services.flashcard_service import generate_flashcards
            topic = payload.get("topic", "BIS Standards")
            num = payload.get("num_cards", 10)
            loop = asyncio.new_event_loop()
            cards = loop.run_until_complete(generate_flashcards(topic, num_cards=num))
            loop.close()
            result = {"topic": topic, "flashcards": cards}

        else:
            result = {"message": f"Task type '{task_type}' processed (in-memory mode)."}

        _task_registry[task_id]["status"] = "success"
        _task_registry[task_id]["result"] = result
    except Exception as exc:
        _task_registry[task_id]["status"] = "failure"
        _task_registry[task_id]["error"] = str(exc)
        logger.error(f"In-memory task {task_id} failed: {exc}")

    return task_id


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", status_code=202, response_model=TaskStatusResponse)
def submit_task(body: TaskSubmitRequest):
    """Submit an async background task. Returns task_id for status polling."""
    valid_types = {"batch_compliance_check", "generate_flashcards", "process_document"}
    if body.task_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task_type '{body.task_type}'. Valid: {sorted(valid_types)}",
        )

    try:
        from app.workers.celery_app import celery_app, CELERY_AVAILABLE
        if CELERY_AVAILABLE and celery_app:
            task_map = {
                "batch_compliance_check": "tasks.batch_compliance_check",
                "generate_flashcards": "tasks.generate_flashcards_async",
                "process_document": "tasks.process_document",
            }
            celery_task_name = task_map[body.task_type]
            task = celery_app.send_task(celery_task_name, kwargs=body.payload)
            task_id = task.id
            logger.info(f"Celery task submitted: {task_id} ({body.task_type})")
            _task_registry[task_id] = {"task_id": task_id, "task_type": body.task_type, "status": "pending"}
            return TaskStatusResponse(task_id=task_id, task_type=body.task_type, status="pending")
    except Exception as exc:
        logger.warning(f"Celery unavailable ({exc}), running task in-memory.")

    # Fallback: run synchronously
    task_id = _submit_in_memory(body.task_type, body.payload)
    reg = _task_registry[task_id]
    return TaskStatusResponse(
        task_id=task_id,
        task_type=body.task_type,
        status=reg["status"],
        result=reg.get("result"),
        error=reg.get("error"),
    )


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    """Poll the status of a submitted task."""
    # Try Celery first
    try:
        from app.workers.celery_app import celery_app, CELERY_AVAILABLE
        if CELERY_AVAILABLE and celery_app:
            from celery.result import AsyncResult  # type: ignore
            async_result = AsyncResult(task_id, app=celery_app)
            state = async_result.state.lower()
            result = None
            error = None
            if state == "success":
                result = async_result.result
            elif state == "failure":
                error = str(async_result.info)
            task_type = _task_registry.get(task_id, {}).get("task_type", "unknown")
            return TaskStatusResponse(task_id=task_id, task_type=task_type, status=state, result=result, error=error)
    except Exception:
        pass

    # In-memory registry fallback
    reg = _task_registry.get(task_id)
    if not reg:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return TaskStatusResponse(**reg)
