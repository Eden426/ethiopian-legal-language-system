"""SQLite-backed conversation history with append-only audit events."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

CATEGORY = "legal_language"


class ConversationNotFoundError(LookupError):
    """Raised when a conversation ID does not exist."""


@dataclass(frozen=True)
class ConversationRecord:
    """Stored conversation metadata."""

    id: str
    category: str
    title: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MessageRecord:
    """One ordered conversation message."""

    id: str
    conversation_id: str
    role: str
    kind: str
    content: str
    created_at: str


@dataclass(frozen=True)
class AuditRecord:
    """Content-safe append-only audit event."""

    id: int
    conversation_id: str
    action: str
    entity_type: str
    entity_id: str
    metadata: dict[str, str | int]
    occurred_at: str


class HistoryStore:
    """Persist conversations and audit events in one private SQLite file."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @classmethod
    def from_database_url(cls, database_url: str) -> "HistoryStore":
        """Create a store from the MVP's SQLite URL."""

        prefix = "sqlite:///"
        if not database_url.startswith(prefix):
            raise ValueError("Conversation history currently requires a sqlite:/// database URL")
        return cls(database_url.removeprefix(prefix))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        """Create the MVP schema without replacing existing data."""

        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL CHECK (category = 'legal_language'),
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                    kind TEXT NOT NULL CHECK (kind IN ('translate', 'search', 'answer')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                );

                CREATE INDEX IF NOT EXISTS messages_conversation_order
                    ON messages(conversation_id, created_at);

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                );

                CREATE INDEX IF NOT EXISTS audit_conversation_order
                    ON audit_events(conversation_id, id);
                """
            )

    def create_conversation(self, title: str) -> ConversationRecord:
        """Create a conversation inside the single MVP category."""

        conversation_id = str(uuid4())
        timestamp = _utc_now()
        cleaned_title = title.strip() or "New conversation"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations (id, category, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, CATEGORY, cleaned_title, timestamp, timestamp),
            )
            self._append_audit(
                connection,
                conversation_id=conversation_id,
                action="conversation.created",
                entity_type="conversation",
                entity_id=conversation_id,
                metadata={"category": CATEGORY},
                occurred_at=timestamp,
            )
        return ConversationRecord(
            id=conversation_id,
            category=CATEGORY,
            title=cleaned_title,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def list_conversations(self) -> list[ConversationRecord]:
        """List the single category's conversations, newest first."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, category, title, created_at, updated_at
                FROM conversations
                WHERE category = ?
                ORDER BY updated_at DESC, id DESC
                """,
                (CATEGORY,),
            ).fetchall()
        return [ConversationRecord(**dict(row)) for row in rows]

    def get_conversation(self, conversation_id: str) -> ConversationRecord:
        """Return one conversation or raise a domain-specific error."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, category, title, created_at, updated_at
                FROM conversations
                WHERE id = ? AND category = ?
                """,
                (conversation_id, CATEGORY),
            ).fetchone()
        if row is None:
            raise ConversationNotFoundError(conversation_id)
        return ConversationRecord(**dict(row))

    def add_message(
        self,
        conversation_id: str,
        *,
        role: str,
        kind: str,
        content: str,
    ) -> MessageRecord:
        """Append a message and a content-safe audit event atomically."""

        message_id = str(uuid4())
        timestamp = _utc_now()
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM conversations WHERE id = ? AND category = ?",
                (conversation_id, CATEGORY),
            ).fetchone()
            if exists is None:
                raise ConversationNotFoundError(conversation_id)
            connection.execute(
                """
                INSERT INTO messages (id, conversation_id, role, kind, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (message_id, conversation_id, role, kind, content, timestamp),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (timestamp, conversation_id),
            )
            self._append_audit(
                connection,
                conversation_id=conversation_id,
                action="message.created",
                entity_type="message",
                entity_id=message_id,
                metadata={"role": role, "kind": kind, "content_length": len(content)},
                occurred_at=timestamp,
            )
        return MessageRecord(
            id=message_id,
            conversation_id=conversation_id,
            role=role,
            kind=kind,
            content=content,
            created_at=timestamp,
        )

    def list_messages(self, conversation_id: str) -> list[MessageRecord]:
        """Return all messages in insertion order."""

        self.get_conversation(conversation_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, conversation_id, role, kind, content, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [MessageRecord(**dict(row)) for row in rows]

    def list_audit_events(self, conversation_id: str) -> list[AuditRecord]:
        """Return append-only audit history without message content."""

        self.get_conversation(conversation_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, conversation_id, action, entity_type, entity_id,
                       metadata_json, occurred_at
                FROM audit_events
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [
            AuditRecord(
                id=row["id"],
                conversation_id=row["conversation_id"],
                action=row["action"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                metadata=json.loads(row["metadata_json"]),
                occurred_at=row["occurred_at"],
            )
            for row in rows
        ]

    @staticmethod
    def _append_audit(
        connection: sqlite3.Connection,
        *,
        conversation_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: dict[str, str | int],
        occurred_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_events (
                conversation_id, action, entity_type, entity_id, metadata_json, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                action,
                entity_type,
                entity_id,
                json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                occurred_at,
            ),
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
