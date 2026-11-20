import datetime as dt
from pathlib import Path

import pytest

from fechou.config import ColumnMapping
from fechou.demo_data import DEMO_COLUMNS, generate_sales, write_csv
from fechou.extract.csv_source import CsvSource
from fechou.transform.validate import validate_rows
from tests.conftest import EXAMPLES_DIR, make_table

START = dt.date(2026, 11, 2)
END = dt.date(2026, 11, 15)


def test_is_deterministic_for_a_seed() -> None:
    assert generate_sales(START, END, seed=7) == generate_sales(START, END, seed=7)
    assert generate_sales(START, END, seed=7) != generate_sales(START, END, seed=8)


def test_every_day_in_range_has_only_valid_sales(columns: ColumnMapping) -> None:
    rows = generate_sales(START, END)
    table = make_table([[row[field] for field in DEMO_COLUMNS] for row in rows])

    result = validate_rows(table, columns)

    assert result.invalid == ()
    days = {row.date for row in result.valid}
    assert days == {START + dt.timedelta(days=n) for n in range((END - START).days + 1)}


def test_invalid_rows_are_injected(tmp_path: Path, columns: ColumnMapping) -> None:
    rows = generate_sales(START, END, invalid_rows=6)
    path = tmp_path / "demo.csv"
    write_csv(rows, path)

    result = validate_rows(CsvSource("demo", path).read(), columns)

    assert result.total == len(rows)
    assert len(result.invalid) == 6


def test_rejects_inverted_range() -> None:
    with pytest.raises(ValueError):
        generate_sales(END, START)


def test_committed_demo_csv_matches_generator(tmp_path: Path) -> None:
    """examples/vendas_demo.csv must be reproducible with the script defaults."""
    rows = generate_sales(dt.date(2026, 9, 7), dt.date(2026, 11, 15), seed=42, invalid_rows=6)
    path = tmp_path / "vendas_demo.csv"
    write_csv(rows, path)

    expected = (EXAMPLES_DIR / "vendas_demo.csv").read_bytes().replace(b"\r\n", b"\n")
    assert path.read_bytes() == expected
