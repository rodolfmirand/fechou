"""SQLite log of executions and the idempotency check (RF-10, RF-11).

``run_key`` = ``source_id:start:end``. A partial unique index guarantees at
most one *regular* successful delivery per key; ``--force`` re-sends are
recorded with ``forced = 1`` and do not collide with it.
"""

import datetime as dt
import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from fechou.domain.period import Period
from fechou.errors import FechouError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT    NOT NULL,
    run_key         TEXT    NOT NULL,
    source_id       TEXT    NOT NULL,
    period_start    TEXT    NOT NULL,
    period_end      TEXT    NOT NULL,
    status          TEXT    NOT NULL,
    forced          INTEGER NOT NULL DEFAULT 0,
    rows_total      INTEGER,
    rows_invalid    INTEGER,
    recipients      TEXT    NOT NULL DEFAULT '[]',
    error_message   TEXT,
    created_at      TEXT    NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_runs_success_key
    ON runs (run_key) WHERE status = 'success' AND forced = 0;
CREATE INDEX IF NOT EXISTS ix_runs_key_status ON runs (run_key, status);
"""

ERROR_MESSAGE_LIMIT = 500


class RunStatus(StrEnum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    DELIVERY_FAILED = "delivery_failed"
    ERROR = "error"
    DRY_RUN = "dry_run"  # extension: dry runs are logged but never count as "sent"


class StorageError(FechouError):
    """The runs database could not be used."""


def make_run_key(source_id: str, period: Period) -> str:
    return f"{source_id}:{period.key}"


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    run_key: str
    source_id: str
    period: Period
    status: RunStatus
    forced: bool
    rows_total: int | None
    rows_invalid: int | None
    recipients: tuple[str, ...]
    error_message: str | None
    created_at: dt.datetime


class RunStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as conn:
                conn.executescript(_SCHEMA)
        except (OSError, sqlite3.Error) as exc:
            raise StorageError(
                f"Não foi possível abrir o banco de execuções {path}: {exc}"
            ) from None

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path, timeout=10)) as conn:
            conn.row_factory = sqlite3.Row
            with conn:  # commit on success, rollback on error
                yield conn

    def last_success(self, run_key: str) -> RunRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_key = ? AND status = ? ORDER BY id DESC LIMIT 1",
                (run_key, RunStatus.SUCCESS.value),
            ).fetchone()
        return _to_record(row) if row else None

    def record(
        self,
        *,
        run_id: str,
        source_id: str,
        period: Period,
        status: RunStatus,
        forced: bool = False,
        rows_total: int | None = None,
        rows_invalid: int | None = None,
        recipients: Sequence[str] = (),
        error_message: str | None = None,
        now: dt.datetime | None = None,
    ) -> RunRecord:
        created_at = (now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC)
        message = error_message[:ERROR_MESSAGE_LIMIT] if error_message else None
        run_key = make_run_key(source_id, period)
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO runs (run_id, run_key, source_id, period_start, period_end, "
                    "status, forced, rows_total, rows_invalid, recipients, error_message, "
                    "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        run_key,
                        source_id,
                        period.start.isoformat(),
                        period.end.isoformat(),
                        status.value,
                        int(forced),
                        rows_total,
                        rows_invalid,
                        json.dumps(list(recipients)),
                        message,
                        created_at.isoformat(),
                    ),
                )
        except sqlite3.Error as exc:
            raise StorageError(f"Não foi possível registrar a execução: {exc}") from None
        return RunRecord(
            run_id=run_id,
            run_key=run_key,
            source_id=source_id,
            period=period,
            status=status,
            forced=forced,
            rows_total=rows_total,
            rows_invalid=rows_invalid,
            recipients=tuple(recipients),
            error_message=message,
            created_at=created_at,
        )

    def history(self, limit: int = 20) -> list[RunRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [_to_record(row) for row in rows]


def _to_record(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        run_id=row["run_id"],
        run_key=row["run_key"],
        source_id=row["source_id"],
        period=Period(
            dt.date.fromisoformat(row["period_start"]), dt.date.fromisoformat(row["period_end"])
        ),
        status=RunStatus(row["status"]),
        forced=bool(row["forced"]),
        rows_total=row["rows_total"],
        rows_invalid=row["rows_invalid"],
        recipients=tuple(json.loads(row["recipients"])),
        error_message=row["error_message"],
        created_at=dt.datetime.fromisoformat(row["created_at"]),
    )
