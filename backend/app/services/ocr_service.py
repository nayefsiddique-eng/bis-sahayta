"""
OCR service with provider abstraction.
Providers: TesseractProvider, MockProvider.
Selection driven by settings.OCR_PROVIDER env var.
"""
from __future__ import annotations

import io
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class OCRProvider(ABC):
    @abstractmethod
    async def extract_text(self, image_bytes: bytes, lang: str = "eng") -> str:
        """Extract text from image bytes. Returns plain text."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...


# ---------------------------------------------------------------------------
# MockProvider (tests / dev)
# ---------------------------------------------------------------------------

class MockOCRProvider(OCRProvider):
    name = "mock"

    async def extract_text(self, image_bytes: bytes, lang: str = "eng") -> str:
        logger.debug("MockOCRProvider.extract_text called")
        size_kb = len(image_bytes) / 1024
        return (
            f"[MockOCR] Extracted text from image ({size_kb:.1f} KB, lang={lang}).\n"
            "This is placeholder OCR output. Configure OCR_PROVIDER=tesseract with "
            "Tesseract installed to enable real OCR."
        )


# ---------------------------------------------------------------------------
# TesseractProvider
# ---------------------------------------------------------------------------

class TesseractProvider(OCRProvider):
    name = "tesseract"

    def __init__(self) -> None:
        try:
            import pytesseract  # type: ignore
            if settings.TESSERACT_CMD:
                pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
            self._pytesseract = pytesseract
        except ImportError as exc:
            raise RuntimeError(
                "pytesseract is not installed. Run: pip install pytesseract"
            ) from exc

    async def extract_text(self, image_bytes: bytes, lang: str = "eng") -> str:
        import asyncio
        from PIL import Image  # type: ignore

        img = Image.open(io.BytesIO(image_bytes))

        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            None,
            lambda: self._pytesseract.image_to_string(img, lang=lang),
        )
        return text.strip()


# ---------------------------------------------------------------------------
# PDF text extraction (non-OCR, faster for PDFs with embedded text)
# ---------------------------------------------------------------------------

async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract embedded text from a PDF using PyMuPDF (fitz). No OCR needed."""
    try:
        import pymupdf as fitz  # type: ignore
    except ImportError:
        try:
            import fitz  # type: ignore (older PyMuPDF API)
        except ImportError:
            return ""

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages_text = []
        for page in doc:
            pages_text.append(page.get_text())
        doc.close()
        return "\n\n".join(pages_text).strip()
    except Exception as exc:
        logger.debug(f"PDF text extraction failed (may not be a valid PDF): {exc}")
        return ""


# ---------------------------------------------------------------------------
# Factory singleton
# ---------------------------------------------------------------------------

_ocr_provider: OCRProvider | None = None


def get_ocr_provider() -> OCRProvider:
    global _ocr_provider
    if _ocr_provider is None:
        name = settings.OCR_PROVIDER.lower().strip()
        if name == "tesseract":
            try:
                _ocr_provider = TesseractProvider()
            except RuntimeError as exc:
                logger.warning(f"TesseractProvider init failed ({exc}), falling back to MockOCR.")
                _ocr_provider = MockOCRProvider()
        else:
            if name not in ("mock", ""):
                logger.warning(f"Unknown OCR_PROVIDER='{name}', using MockOCRProvider.")
            _ocr_provider = MockOCRProvider()
        logger.info(f"OCRService using provider: {_ocr_provider.name}")
    return _ocr_provider


class OCRService:
    """Public facade for OCR operations."""

    @staticmethod
    async def extract_text(
        file_bytes: bytes,
        mime_type: str = "image/jpeg",
        lang: str = "eng",
        provider: OCRProvider | None = None,
    ) -> str:
        """
        Extract text from image or PDF bytes.

        For PDFs, attempts fast embedded-text extraction first.
        Falls back to image OCR if the extracted text is too short.
        """
        if mime_type == "application/pdf":
            text = await extract_text_from_pdf(file_bytes)
            if len(text) > 50:
                return text
            # Fall through to OCR for scanned PDFs (no embedded text)
            logger.info("PDF appears to be scanned — falling back to OCR pipeline.")

        p = provider or get_ocr_provider()
        return await p.extract_text(file_bytes, lang=lang)
