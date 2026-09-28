"""
Document management router.
POST /documents/upload  — upload a document (PDF/image), extract text, index metadata
GET  /documents/{id}    — retrieve document metadata + extracted text
DELETE /documents/{id}  — delete document record
POST /documents/scan    — scan bytes directly (inline OCR, no storage)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.core.config import settings
from app.services.ocr_service import OCRService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = Path(settings.UPLOAD_DIR)
META_DB_FILE = UPLOAD_DIR / "documents_meta.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_upload_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _load_meta_db() -> dict:
    if META_DB_FILE.exists():
        try:
            return json.loads(META_DB_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_meta_db(db: dict) -> None:
    _ensure_upload_dir()
    META_DB_FILE.write_text(json.dumps(db, indent=2, default=str), encoding="utf-8")


def _validate_upload(file: UploadFile, data: bytes) -> None:
    # Size check
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )
    # MIME check
    content_type = (file.content_type or "").split(";")[0].strip()
    if content_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: '{content_type}'. Allowed: {settings.ALLOWED_MIME_TYPES}",
        )
    # Path traversal: sanitize filename
    if file.filename and (".." in file.filename or "/" in file.filename or "\\" in file.filename):
        raise HTTPException(status_code=400, detail="Invalid filename.")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DocumentMeta(BaseModel):
    document_id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    uploaded_at: str
    extracted_text_preview: str  # first 500 chars
    full_text_available: bool


class ScanRequest(BaseModel):
    text: str
    lang: str = "en"
    content_type: str = "image/jpeg"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload", status_code=201, response_model=DocumentMeta)
async def upload_document(
    file: UploadFile = File(...),
    lang: str = Query("eng", description="OCR language hint (Tesseract lang code, e.g. 'eng', 'hin')"),
):
    """Upload a document (PDF/image). Extracts text, stores file, returns metadata."""
    _ensure_upload_dir()
    data = await file.read()
    _validate_upload(file, data)

    content_type = (file.content_type or "application/octet-stream").split(";")[0].strip()
    doc_id = f"doc-{uuid.uuid4().hex[:12]}"
    sha256 = hashlib.sha256(data).hexdigest()

    # Save file
    ext = Path(file.filename or "upload").suffix or ".bin"
    saved_path = UPLOAD_DIR / f"{doc_id}{ext}"
    saved_path.write_bytes(data)

    # Extract text
    extracted_text = await OCRService.extract_text(data, mime_type=content_type, lang=lang)

    # Save full text separately
    text_path = UPLOAD_DIR / f"{doc_id}.txt"
    text_path.write_text(extracted_text, encoding="utf-8")

    # Persist metadata
    now = datetime.now(timezone.utc).isoformat()
    meta = {
        "document_id": doc_id,
        "filename": file.filename or "unknown",
        "content_type": content_type,
        "size_bytes": len(data),
        "sha256": sha256,
        "uploaded_at": now,
        "file_path": str(saved_path),
        "text_path": str(text_path),
        "extracted_text_preview": extracted_text[:500],
        "full_text_available": bool(extracted_text),
    }
    db = _load_meta_db()
    db[doc_id] = meta
    _save_meta_db(db)

    logger.info(f"Document uploaded: {doc_id} ({len(data)} bytes, type={content_type})")
    return DocumentMeta(**meta)


@router.get("/{document_id}", response_model=DocumentMeta)
def get_document(document_id: str, full_text: bool = Query(False)):
    """Retrieve document metadata. Optionally include full extracted text."""
    db = _load_meta_db()
    meta = db.get(document_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    result = dict(meta)
    if full_text:
        text_path = Path(meta.get("text_path", ""))
        if text_path.exists():
            result["extracted_text_preview"] = text_path.read_text(encoding="utf-8")
    return DocumentMeta(**result)


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str):
    """Delete a document and its extracted text from storage."""
    db = _load_meta_db()
    meta = db.get(document_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    # Remove files
    for key in ("file_path", "text_path"):
        p = Path(meta.get(key, ""))
        if p.exists():
            try:
                p.unlink()
            except Exception as exc:
                logger.warning(f"Could not delete {p}: {exc}")

    del db[document_id]
    _save_meta_db(db)
    logger.info(f"Document deleted: {document_id}")


@router.post("/scan")
async def scan_document(
    file: UploadFile = File(...),
    lang: str = Query("eng"),
):
    """
    Scan a document inline — performs OCR and returns extracted text without storing the file.
    """
    data = await file.read()
    _validate_upload(file, data)
    content_type = (file.content_type or "image/jpeg").split(";")[0].strip()
    extracted = await OCRService.extract_text(data, mime_type=content_type, lang=lang)
    return {
        "filename": file.filename,
        "content_type": content_type,
        "size_bytes": len(data),
        "extracted_text": extracted,
        "char_count": len(extracted),
    }
