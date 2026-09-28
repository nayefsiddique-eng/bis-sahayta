"""
RAG (Retrieval-Augmented Generation) service.
Wraps the pre-built FAISS vector store from the MAIN backend.
Gracefully degrades if the vector store is not available.
"""
from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class RetrievedChunk:
    def __init__(self, text: str, metadata: dict, score: float = 0.0) -> None:
        self.text = text
        self.metadata = metadata
        self.score = score

    def to_dict(self) -> dict:
        return {"text": self.text, "metadata": self.metadata, "score": self.score}


# ---------------------------------------------------------------------------
# Vector store loader (FAISS + sentence-transformers)
# ---------------------------------------------------------------------------

class _VectorStore:
    """Wraps the FAISS index + metadata from MAIN backend storage."""

    def __init__(self, vectorstore_path: str) -> None:
        self._available = False
        self._index = None
        self._documents: list[str] = []
        self._metadata: list[dict] = []
        self._model = None
        self._load(vectorstore_path)

    def _load(self, path: str) -> None:
        vs_dir = Path(path)
        index_file = vs_dir / "bis_documents.index"
        meta_file = vs_dir / "bis_documents_metadata.pkl"
        docs_file = vs_dir / "bis_documents_documents.pkl"

        if not index_file.exists():
            logger.warning(
                f"FAISS index not found at {index_file}. RAG will be unavailable. "
                "Ensure VECTORSTORE_PATH points to the storage/vectorstore directory."
            )
            return

        try:
            import faiss  # type: ignore
            import os
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._index = faiss.read_index(str(index_file))

            if meta_file.exists():
                with open(meta_file, "rb") as f:
                    self._metadata = pickle.load(f)
            else:
                self._metadata = [{} for _ in range(self._index.ntotal)]

            if docs_file.exists():
                with open(docs_file, "rb") as f:
                    self._documents = pickle.load(f)
            else:
                self._documents = [""] * self._index.ntotal

            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            self._available = True
            logger.info(
                f"RAG vector store loaded: {self._index.ntotal} chunks, "
                f"model={settings.EMBEDDING_MODEL}"
            )
        except ImportError as exc:
            logger.warning(f"RAG dependencies not installed ({exc}). RAG disabled.")
        except Exception as exc:
            logger.error(f"Failed to load vector store: {exc}")

    @property
    def available(self) -> bool:
        return self._available

    def search(self, query: str, k: int = 5) -> list[RetrievedChunk]:
        if not self._available or self._model is None or self._index is None:
            return []
        try:
            import numpy as np
            embedding = self._model.encode([query], convert_to_numpy=True)
            distances, indices = self._index.search(embedding, k)
            results: list[RetrievedChunk] = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx < 0 or idx >= len(self._documents):
                    continue
                text = self._documents[idx] if idx < len(self._documents) else ""
                meta = self._metadata[idx] if idx < len(self._metadata) else {}
                # Convert L2 distance to similarity score (lower = better for L2)
                score = float(1.0 / (1.0 + dist))
                results.append(RetrievedChunk(text=text, metadata=meta, score=score))
            return results
        except Exception as exc:
            logger.error(f"Vector search error: {exc}")
            return []


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_vector_store: Optional[_VectorStore] = None


def get_vector_store() -> _VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = _VectorStore(settings.VECTORSTORE_PATH)
    return _vector_store


# ---------------------------------------------------------------------------
# Public RAGService
# ---------------------------------------------------------------------------

class RAGService:
    """Public facade for RAG retrieval."""

    @staticmethod
    def is_available() -> bool:
        return get_vector_store().available

    @staticmethod
    def retrieve(query: str, k: int = None) -> list[RetrievedChunk]:
        """Return top-k relevant document chunks for the query."""
        top_k = k or settings.RAG_TOP_K
        return get_vector_store().search(query, k=top_k)

    @staticmethod
    def retrieve_texts(query: str, k: int = None) -> list[str]:
        """Convenience method — returns only text strings."""
        return [c.text for c in RAGService.retrieve(query, k=k)]

    @staticmethod
    def retrieve_with_metadata(query: str, k: int = None) -> list[dict]:
        """Returns list of dicts with text + metadata + score."""
        return [c.to_dict() for c in RAGService.retrieve(query, k=k)]
