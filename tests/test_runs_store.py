import datetime as dt
import sqlite3
from pathlib import Path

import pytest

from fechou.domain.period import Period
from fechou.storage.runs import ERROR_MESSAGE_LIMIT, RunStatus, RunStore, StorageError

WEEK = Period(dt.date(2026, 11, 9), dt.date(2026, 11, 15))
NOW = dt.datetime(2026, 11, 16, 7, 0, tzinfo=dt.timezone(dt.timedelta(hours=-3)))


@pytest.fixture
def store(tmp_path: Path) -> RunStore:
    return RunStore(tmp_path / "data" / "fechou.db")


def test_creates_database_and_parent_folder(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "fechou.db"

    RunStore(path)

    assert path.exists()


def test_record_round_trip(store: RunStore) -> None:
    store.record(
        run_id="abc",
        source_id="loja",
        period=WEEK,
        status=RunStatus.SUCCESS,
        rows_total=10,
        rows_invalid=1,
        recipients=["dono@exemplo.com"],
        now=NOW,
    )

    record = store.last_success("loja:2026-11-09:2026-11-15")

    assert record is not None
    assert record.run_id == "abc"
    assert record.period == WEEK
    assert record.recipients == ("dono@exemplo.com",)
    assert (record.rows_total, record.rows_invalid) == (10, 1)
    assert record.created_at == NOW  # stored in UTC, same instant
    assert record.created_at.utcoffset() == dt.timedelta(0)


@pytest.mark.parametrize(
    "status",
    [RunStatus.SKIPPED, RunStatus.ERROR, RunStatus.DELIVERY_FAILED, RunStatus.DRY_RUN],
)
def test_only_success_counts_as_sent(store: RunStore, status: RunStatus) -> None:
    store.record(run_id="x", source_id="loja", period=WEEK, status=status)

    assert store.last_success("loja:2026-11-09:2026-11-15") is None


def test_keys_are_per_source_and_period(store: RunStore) -> None:
    store.record(run_id="x", source_id="loja", period=WEEK, status=RunStatus.SUCCESS)

    assert store.last_success("outra-loja:2026-11-09:2026-11-15") is None
    assert store.last_success("loja:2026-11-02:2026-11-08") is None


def test_second_regular_success_for_same_key_is_rejected(store: RunStore) -> None:
    store.record(run_id="a", source_id="loja", period=WEEK, status=RunStatus.SUCCESS)

    with pytest.raises(StorageError):
        store.record(run_id="b", source_id="loja", period=WEEK, status=RunStatus.SUCCESS)


def test_forced_success_is_allowed_and_becomes_the_latest(store: RunStore) -> None:
    store.record(run_id="a", source_id="loja", period=WEEK, status=RunStatus.SUCCESS)
    store.record(run_id="b", source_id="loja", period=WEEK, status=RunStatus.SUCCESS, forced=True)

    latest = store.last_success("loja:2026-11-09:2026-11-15")

    assert latest is not None
    assert (latest.run_id, latest.forced) == ("b", True)
    assert [r.run_id for r in store.history()] == ["b", "a"]


def test_error_message_is_truncated(store: RunStore) -> None:
    record = store.record(
        run_id="x", source_id="loja", period=WEEK, status=RunStatus.ERROR, error_message="e" * 2000
    )

    assert record.error_message is not None
    assert len(record.error_message) == ERROR_MESSAGE_LIMIT


def test_schema_matches_specification(store: RunStore) -> None:
    with sqlite3.connect(store.path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}

    assert {
        "id",
        "run_key",
        "source_id",
        "period_start",
        "period_end",
        "status",
        "rows_total",
        "rows_invalid",
        "recipients",
        "error_message",
        "created_at",
    } <= columns


def test_unusable_path_raises_storage_error(tmp_path: Path) -> None:
    blocker = tmp_path / "arquivo"
    blocker.write_text("x", encoding="utf-8")

    with pytest.raises(StorageError):
        RunStore(blocker / "fechou.db")
