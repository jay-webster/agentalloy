"""Local, deduped store of candidate AI-innovation items found in email.

Deliberately not DuckDB: this is a single append-mostly log with one writer
and one reader, not an analytical store — sqlite3 (stdlib) is the simplest
tool that's actually correct here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB_PATH = Path(".automation") / "candidates.db"

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS candidates (
    message_id  TEXT PRIMARY KEY,
    thread_id   TEXT NOT NULL,
    source      TEXT NOT NULL,
    subject     TEXT NOT NULL,
    received_at TEXT NOT NULL,
    snippet     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'new',
    ingested_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Candidate:
    message_id: str
    thread_id: str
    source: str
    subject: str
    received_at: str
    snippet: str
    ingested_at: str
    status: str = "new"


class CandidateStore:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(_SCHEMA_DDL)
        self._conn.commit()

    def add(self, candidate: Candidate) -> bool:
        cursor = self._conn.execute(
            """
            INSERT INTO candidates
                (message_id, thread_id, source, subject, received_at, snippet, status, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO NOTHING
            """,
            (
                candidate.message_id,
                candidate.thread_id,
                candidate.source,
                candidate.subject,
                candidate.received_at,
                candidate.snippet,
                candidate.status,
                candidate.ingested_at,
            ),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def list(self, status: str | None = None) -> list[Candidate]:
        if status is None:
            rows = self._conn.execute(
                "SELECT message_id, thread_id, source, subject, received_at, "
                "snippet, status, ingested_at FROM candidates ORDER BY ingested_at"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT message_id, thread_id, source, subject, received_at, "
                "snippet, status, ingested_at FROM candidates WHERE status = ? "
                "ORDER BY ingested_at",
                (status,),
            ).fetchall()
        return [
            Candidate(
                message_id=r[0],
                thread_id=r[1],
                source=r[2],
                subject=r[3],
                received_at=r[4],
                snippet=r[5],
                status=r[6],
                ingested_at=r[7],
            )
            for r in rows
        ]

    def mark(self, message_id: str, status: str) -> bool:
        cursor = self._conn.execute(
            "UPDATE candidates SET status = ? WHERE message_id = ?",
            (status, message_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        self._conn.close()
