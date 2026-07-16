"""Local, deduped store of candidate AI-innovation items found in email.

Deliberately not DuckDB: this is a single append-mostly log with one writer
and one reader, not an analytical store — sqlite3 (stdlib) is the simplest
tool that's actually correct here.
"""

from __future__ import annotations

import datetime
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from automation import injection_guard, integrator, url_ingest

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

CREATE TABLE IF NOT EXISTS ingest_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_NEW_COLUMNS = {
    "verdict": "TEXT",
    "rationale": "TEXT",
    "evaluated_at": "TEXT",
    "flagged": "INTEGER",
    "flag_reasons": "TEXT",
    "integrated_at": "TEXT",
    "integration_slug": "TEXT",
}

VALID_VERDICTS = frozenset({"accept", "reject", "needs_review"})

INTAKE_DRAFTS_DIR = Path("automation") / "intake-drafts"


class FlaggedCandidateError(Exception):
    def __init__(self, message_id: str, flag_reasons: str) -> None:
        self.message_id = message_id
        self.flag_reasons = flag_reasons
        super().__init__(
            f"{message_id} is flagged ({flag_reasons}) — accept is blocked, "
            "use reject or needs_review"
        )


class NotAcceptedError(Exception):
    def __init__(self, message_id: str, verdict: str | None) -> None:
        self.message_id = message_id
        self.verdict = verdict
        super().__init__(
            f"{message_id} cannot be integrated: verdict is {verdict!r}, "
            "only accept candidates can be integrated"
        )


class CandidateNotFoundError(Exception):
    def __init__(self, message_id: str) -> None:
        self.message_id = message_id
        super().__init__(f"no candidate with message_id {message_id}")


@dataclass(frozen=True)
class IntegrationResult:
    slug: str
    draft_path: Path
    already_existed: bool


@dataclass
class BatchEvaluationResult:
    evaluated: list[str]
    refused: list[tuple[str, str]]
    not_found: list[str]


def _ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(candidates)")}
    for name, sql_type in _NEW_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE candidates ADD COLUMN {name} {sql_type}")
    conn.commit()


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
    verdict: str | None = None
    rationale: str | None = None
    evaluated_at: str | None = None
    flagged: bool = False
    flag_reasons: str = ""
    integrated_at: str | None = None
    integration_slug: str | None = None


class CandidateStore:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(_SCHEMA_DDL)
        self._conn.commit()
        _ensure_columns(self._conn)

    def add(self, candidate: Candidate) -> bool:
        reasons = injection_guard.screen(f"{candidate.subject} {candidate.snippet}")
        cursor = self._conn.execute(
            """
            INSERT INTO candidates
                (message_id, thread_id, source, subject, received_at, snippet, status,
                 ingested_at, flagged, flag_reasons)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                1 if reasons else 0,
                ", ".join(reasons),
            ),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def get_state(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM ingest_state WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_state(self, key: str, value: str) -> None:
        self._conn.execute(
            """
            INSERT INTO ingest_state (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self._conn.commit()

    def find_by_url(self, url: str) -> str | None:
        prefix = f"URL: {url}"
        rows = self._conn.execute("SELECT message_id, snippet FROM candidates").fetchall()
        for message_id, snippet in rows:
            if snippet == prefix or snippet.startswith(prefix + "\n"):
                return message_id
        return None

    def add_url(
        self, url: str, subject: str, received_at: str, source: str = "discord"
    ) -> tuple[str, bool]:
        existing = self.find_by_url(url)
        if existing is not None:
            return existing, False

        message_id = url_ingest.candidate_id_for_url(url)
        candidate = Candidate(
            message_id=message_id,
            thread_id=message_id,
            source=source,
            subject=subject,
            received_at=received_at,
            snippet=f"URL: {url}",
            ingested_at=datetime.datetime.now(datetime.UTC).isoformat(),
        )
        self.add(candidate)
        return message_id, True

    def list(self, status: str | None = None) -> list[Candidate]:
        columns = (
            "message_id, thread_id, source, subject, received_at, snippet, "
            "status, ingested_at, verdict, rationale, evaluated_at, flagged, flag_reasons, "
            "integrated_at, integration_slug"
        )
        if status is None:
            rows = self._conn.execute(
                f"SELECT {columns} FROM candidates ORDER BY ingested_at"
            ).fetchall()
        else:
            rows = self._conn.execute(
                f"SELECT {columns} FROM candidates WHERE status = ? ORDER BY ingested_at",
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
                verdict=r[8],
                rationale=r[9],
                evaluated_at=r[10],
                flagged=bool(r[11]),
                flag_reasons=r[12] or "",
                integrated_at=r[13],
                integration_slug=r[14],
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

    def evaluate(self, message_id: str, verdict: str, rationale: str) -> bool:
        if verdict not in VALID_VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(VALID_VERDICTS)}, got {verdict!r}")
        if verdict == "accept":
            row = self._conn.execute(
                "SELECT flagged, flag_reasons FROM candidates WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if row is not None and row[0]:
                raise FlaggedCandidateError(message_id, row[1] or "")
        evaluated_at = datetime.datetime.now(datetime.UTC).isoformat()
        cursor = self._conn.execute(
            "UPDATE candidates SET status = 'evaluated', verdict = ?, "
            "rationale = ?, evaluated_at = ? WHERE message_id = ?",
            (verdict, rationale, evaluated_at, message_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def evaluate_batch(self, rows: list[tuple[str, str, str]]) -> BatchEvaluationResult:
        result = BatchEvaluationResult(evaluated=[], refused=[], not_found=[])
        for message_id, verdict, rationale in rows:
            try:
                found = self.evaluate(message_id, verdict, rationale)
            except FlaggedCandidateError as exc:
                result.refused.append((message_id, exc.flag_reasons))
                continue
            if found:
                result.evaluated.append(message_id)
            else:
                result.not_found.append(message_id)
        return result

    def integrate(self, message_id: str) -> IntegrationResult:
        row = self._conn.execute(
            "SELECT verdict, integrated_at, integration_slug, thread_id, source, "
            "subject, received_at, snippet, ingested_at, status, rationale, "
            "evaluated_at, flagged, flag_reasons FROM candidates WHERE message_id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            raise CandidateNotFoundError(message_id)
        (
            verdict,
            integrated_at,
            integration_slug,
            thread_id,
            source,
            subject,
            received_at,
            snippet,
            ingested_at,
            status,
            rationale,
            evaluated_at,
            flagged,
            flag_reasons,
        ) = row
        if verdict != "accept":
            raise NotAcceptedError(message_id, verdict)
        if integrated_at is not None:
            return IntegrationResult(
                slug=integration_slug,
                draft_path=INTAKE_DRAFTS_DIR / f"{integration_slug}.md",
                already_existed=True,
            )

        candidate = Candidate(
            message_id=message_id,
            thread_id=thread_id,
            source=source,
            subject=subject,
            received_at=received_at,
            snippet=snippet,
            ingested_at=ingested_at,
            status=status,
            verdict=verdict,
            rationale=rationale,
            evaluated_at=evaluated_at,
            flagged=bool(flagged),
            flag_reasons=flag_reasons or "",
        )
        slug = integrator.slugify(subject, message_id)
        draft_path = INTAKE_DRAFTS_DIR / f"{slug}.md"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(integrator.render_draft(candidate, slug))

        now = datetime.datetime.now(datetime.UTC).isoformat()
        self._conn.execute(
            "UPDATE candidates SET integrated_at = ?, integration_slug = ? WHERE message_id = ?",
            (now, slug, message_id),
        )
        self._conn.commit()
        return IntegrationResult(slug=slug, draft_path=draft_path, already_existed=False)

    def close(self) -> None:
        self._conn.close()
