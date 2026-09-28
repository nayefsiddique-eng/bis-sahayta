"""
Session database — SQLite-backed chat history.
Adapted from MAIN backend/database.py with async support.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)
_lock = threading.Lock()


def _get_db_path() -> Path:
    return Path(settings.SESSION_DB_PATH)


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_get_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _lock:
        conn = _get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id   TEXT PRIMARY KEY,
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    context      TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id   TEXT NOT NULL,
                    role         TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content      TEXT NOT NULL,
                    created_at   TEXT NOT NULL,
                    metadata     TEXT DEFAULT '{}',
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id);
            """)
            conn.commit()
        finally:
            conn.close()


# Initialize on module load
_init_db()


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

def create_session(context: dict = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    session_id = str(uuid.uuid4())
    ctx = json.dumps(context or {})
    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO sessions(session_id, created_at, updated_at, context) VALUES (?,?,?,?)",
                (session_id, now, now, ctx),
            )
            conn.commit()
        finally:
            conn.close()
    return {"session_id": session_id, "created_at": now, "context": context or {}}


def get_session(session_id: str) -> Optional[dict]:
    with _lock:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        finally:
            conn.close()
    if not row:
        return None
    return {
        "session_id": row["session_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "context": json.loads(row["context"] or "{}"),
    }


def update_session_context(session_id: str, context: dict) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _get_conn()
        try:
            cur = conn.execute(
                "UPDATE sessions SET context=?, updated_at=? WHERE session_id=?",
                (json.dumps(context), now, session_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def list_sessions(limit: int = 50) -> list[dict]:
    with _lock:
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        finally:
            conn.close()
    return [
        {
            "session_id": r["session_id"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Message CRUD
# ---------------------------------------------------------------------------

def add_message(session_id: str, role: str, content: str, metadata: dict = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    meta = json.dumps(metadata or {})
    with _lock:
        conn = _get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO messages(session_id, role, content, created_at, metadata) VALUES (?,?,?,?,?)",
                (session_id, role, content, now, meta),
            )
            conn.commit()
            msg_id = cur.lastrowid
        finally:
            conn.close()
    return {"id": msg_id, "session_id": session_id, "role": role, "content": content, "created_at": now}


def delete_session(session_id: str) -> bool:
    """Delete a session and all associated messages."""
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            cur = conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def get_history(session_id: str, limit: int = 50) -> list[dict]:
    with _lock:
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT id, session_id, role, content, created_at, metadata FROM messages "
                "WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        finally:
            conn.close()
    # Return in chronological order
    result = [
        {
            "id": r["id"],
            "session_id": r["session_id"],
            "role": r["role"],
            "content": r["content"],
            "created_at": r["created_at"],
            "metadata": json.loads(r["metadata"] or "{}"),
        }
        for r in rows
    ]
    return list(reversed(result))


def get_history_as_pairs(session_id: str, n_turns: int = 6) -> list[dict]:
    """Return last n_turns turns as [{'user': ..., 'assistant': ...}] pairs."""
    messages = get_history(session_id, limit=n_turns * 2)
    pairs: list[dict] = []
    pair: dict = {}
    for msg in messages:
        if msg["role"] == "user":
            pair = {"user": msg["content"]}
        elif msg["role"] == "assistant" and pair:
            pair["assistant"] = msg["content"]
            pairs.append(pair)
            pair = {}
    return pairs

