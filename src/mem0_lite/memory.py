"""Consent-first, local SQLite memory store."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any


class ConsentRequiredError(PermissionError):
    """Raised when memory is written without explicit user consent."""


class UnsafeMemoryError(ValueError):
    """Raised when content resembles a credential or payment secret."""


_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(password|passwd|api[_ -]?key|access[_ -]?token|secret)\s*[:=]\s*\S+"),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    re.compile(r"(?i)\b(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,})\b"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_user(user_id: str) -> str:
    user_id = str(user_id).strip()
    if not user_id or len(user_id) > 128:
        raise ValueError("user_id must contain 1..128 characters")
    return user_id


class MemoryStore:
    """A small, explicit memory store. No automatic capture is performed."""

    def __init__(self, path: str | Path = "mem0-lite.sqlite3"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        if self.path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS consent (
                user_id TEXT PRIMARY KEY,
                granted INTEGER NOT NULL CHECK (granted IN (0,1)),
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                created_at TEXT NOT NULL,
                expires_at TEXT,
                FOREIGN KEY(user_id) REFERENCES consent(user_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_memories_user_created
                ON memories(user_id, created_at DESC);
        """)
        self._db.commit()

    def grant_consent(self, user_id: str) -> None:
        user_id = _validate_user(user_id)
        with self._lock, self._db:
            self._db.execute(
                """INSERT INTO consent(user_id, granted, updated_at) VALUES(?,1,?)
                   ON CONFLICT(user_id) DO UPDATE SET granted=1, updated_at=excluded.updated_at""",
                (user_id, _utc_now()),
            )

    def revoke_consent(self, user_id: str, delete_existing: bool = True) -> None:
        user_id = _validate_user(user_id)
        with self._lock, self._db:
            self._db.execute(
                """INSERT INTO consent(user_id, granted, updated_at) VALUES(?,0,?)
                   ON CONFLICT(user_id) DO UPDATE SET granted=0, updated_at=excluded.updated_at""",
                (user_id, _utc_now()),
            )
            if delete_existing:
                self._db.execute("DELETE FROM memories WHERE user_id=?", (user_id,))

    def has_consent(self, user_id: str) -> bool:
        user_id = _validate_user(user_id)
        row = self._db.execute("SELECT granted FROM consent WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row["granted"])

    def remember(self, user_id: str, content: str, category: str = "general",
                 expires_in_days: int | None = None) -> int:
        user_id = _validate_user(user_id)
        content = str(content).strip()
        category = str(category).strip() or "general"
        if not content or len(content) > 2000:
            raise ValueError("content must contain 1..2000 characters")
        if len(category) > 64:
            raise ValueError("category must be 64 characters or fewer")
        if any(pattern.search(content) for pattern in _SECRET_PATTERNS):
            raise UnsafeMemoryError("content looks like a credential or payment secret")
        if not self.has_consent(user_id):
            raise ConsentRequiredError("explicit consent is required before saving memory")
        if expires_in_days is not None and not 1 <= int(expires_in_days) <= 3650:
            raise ValueError("expires_in_days must be between 1 and 3650")
        expires = ((datetime.now(timezone.utc) + timedelta(days=int(expires_in_days))).isoformat()
                   if expires_in_days is not None else None)
        with self._lock, self._db:
            cursor = self._db.execute(
                "INSERT INTO memories(user_id,content,category,created_at,expires_at) VALUES(?,?,?,?,?)",
                (user_id, content, category, _utc_now(), expires),
            )
            return int(cursor.lastrowid)

    def search(self, user_id: str, query: str = "", limit: int = 10) -> list[dict[str, Any]]:
        user_id = _validate_user(user_id)
        if not self.has_consent(user_id):
            return []
        limit = max(1, min(int(limit), 100))
        rows = self._db.execute(
            """SELECT id,content,category,created_at,expires_at FROM memories
               WHERE user_id=? AND (expires_at IS NULL OR expires_at>?)
               ORDER BY created_at DESC LIMIT 500""",
            (user_id, _utc_now()),
        ).fetchall()
        terms = [term.casefold() for term in re.findall(r"[\w\u0B80-\u0BFF\u0D80-\u0DFF]+", query)
                 if len(term) > 1]
        scored = []
        for row in rows:
            content = row["content"].casefold()
            score = sum(content.count(term) for term in terms)
            if not terms or score:
                item = dict(row)
                item["score"] = score
                scored.append(item)
        scored.sort(key=lambda item: (item["score"], item["created_at"]), reverse=True)
        return scored[:limit]

    def forget(self, user_id: str, memory_id: int) -> bool:
        user_id = _validate_user(user_id)
        with self._lock, self._db:
            cursor = self._db.execute(
                "DELETE FROM memories WHERE id=? AND user_id=?", (int(memory_id), user_id)
            )
            return cursor.rowcount > 0

    def forget_all(self, user_id: str) -> int:
        user_id = _validate_user(user_id)
        with self._lock, self._db:
            cursor = self._db.execute("DELETE FROM memories WHERE user_id=?", (user_id,))
            return int(cursor.rowcount)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
