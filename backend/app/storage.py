"""Persistent conversation storage with a safe in-memory fallback."""

from __future__ import annotations

import logging
from threading import Lock

from .memory import SessionMemory

logger = logging.getLogger(__name__)


class ConversationStore:
    def __init__(
        self,
        database_url: str = "",
        max_turns: int = 8,
        ttl_seconds: int = 3600,
    ) -> None:
        self._database_url = database_url
        self._fallback = SessionMemory(max_turns=max_turns, ttl_seconds=ttl_seconds)
        self._schema_ready = False
        self._schema_lock = Lock()

    @property
    def persistent(self) -> bool:
        return bool(self._database_url)

    def _connect(self):
        import psycopg

        return psycopg.connect(self._database_url, connect_timeout=10)

    def _ensure_schema(self) -> None:
        if not self.persistent or self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id UUID PRIMARY KEY,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    CREATE TABLE IF NOT EXISTS messages (
                        id BIGSERIAL PRIMARY KEY,
                        conversation_id UUID NOT NULL REFERENCES conversations(id)
                            ON DELETE CASCADE,
                        role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                        content TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS messages_conversation_created_idx
                        ON messages (conversation_id, created_at, id);
                    CREATE TABLE IF NOT EXISTS feedback (
                        id BIGSERIAL PRIMARY KEY,
                        conversation_id UUID REFERENCES conversations(id)
                            ON DELETE SET NULL,
                        message TEXT NOT NULL,
                        rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
            self._schema_ready = True

    def add(self, session_id: str, role: str, content: str) -> None:
        if not self.persistent:
            self._fallback.add(session_id, role, content)
            return
        try:
            self._ensure_schema()
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO conversations (id) VALUES (%s)
                    ON CONFLICT (id) DO UPDATE SET updated_at = NOW()
                    """,
                    (session_id,),
                )
                cursor.execute(
                    """
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (%s, %s, %s)
                    """,
                    (session_id, role, content),
                )
        except Exception:
            logger.exception("Persistent message storage failed; using memory fallback")
            self._fallback.add(session_id, role, content)

    def get(self, session_id: str) -> list[dict]:
        if not self.persistent:
            return self._fallback.get(session_id)
        try:
            self._ensure_schema()
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT role, content FROM messages
                    WHERE conversation_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (session_id, self._fallback.max_messages),
                )
                rows = cursor.fetchall()
            return [
                {"role": role, "content": content}
                for role, content in reversed(rows)
            ]
        except Exception:
            logger.exception("Persistent history lookup failed; using memory fallback")
            return self._fallback.get(session_id)

    def add_feedback(self, session_id: str, message: str, rating: str) -> None:
        if not self.persistent:
            return
        try:
            self._ensure_schema()
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO feedback (conversation_id, message, rating)
                    VALUES (
                        CASE WHEN EXISTS (
                            SELECT 1 FROM conversations WHERE id = %s::uuid
                        ) THEN %s::uuid ELSE NULL END,
                        %s,
                        %s
                    )
                    """,
                    (session_id, session_id, message, rating),
                )
        except Exception:
            logger.exception("Persistent feedback storage failed")
