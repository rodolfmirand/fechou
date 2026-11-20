import datetime as dt
from decimal import Decimal

import pytest

from fechou.config import ColumnMapping
from fechou.errors import SchemaError
from fechou.transform.validate import check_schema, validate_rows
from tests.conftest import make_table

VALID = ["12/11/2026", "Camiseta básica", "Vestuário", "3", "49,90", "Ana"]


def test_all_valid_rows(columns: ColumnMapping) -> None:
    table = make_table([VALID, ["2026-11-13", "Boné", "", "1", "44.90", ""]])

    result = validate_rows(table, columns)

    assert result.total == 2
    assert result.invalid == ()
    assert [row.product for row in result.valid] == ["Camiseta básica", "Boné"]
    assert result.valid[1].date == dt.date(2026, 11, 13)
    assert result.valid[1].category is None
    assert result.valid[1].unit_price == Decimal("44.90")


def test_invalid_rows_are_discarded_with_line_numbers_and_column_labels(
    columns: ColumnMapping,
) -> None:
    table = make_table(
        [
            VALID,  # line 2
            ["31/02/2026", "Boné", "", "1", "10", ""],  # line 3
            VALID,  # line 4
            ["12/11/2026", "", "", "0", "-5", ""],  # line 5
        ]
    )

    result = validate_rows(table, columns)

    assert len(result.valid) == 2
    assert [row.line for row in result.invalid] == [3, 5]
    assert result.invalid[0].errors == (
        "Data: data inválida '31/02/2026' (use dd/mm/aaaa ou aaaa-mm-dd)",
    )
    # Every problem of a line is reported, using the spreadsheet header names.
    labels = [message.split(":")[0] for message in result.invalid[1].errors]
    assert labels == ["Produto", "Qtd", "Preço"]


def test_blank_lines_are_ignored_but_keep_line_numbers(columns: ColumnMapping) -> None:
    table = make_table([VALID, [""] * 6, ["  "] * 6, ["x", "Boné", "", "1", "1", ""]])

    result = validate_rows(table, columns)

    assert result.total == 2
    assert result.invalid[0].line == 5


def test_optional_columns_may_be_unmapped() -> None:
    mapping = ColumnMapping(date="Dia", product="Item", quantity="Quantidade", unit_price="Valor")
    table = make_table(
        [["12/11/2026", "Boné", "2", "44,90"]],
        header=["Dia", "Item", "Quantidade", "Valor"],
    )

    result = validate_rows(table, mapping)

    assert result.valid[0].category is None
    assert result.valid[0].seller is None


def test_extra_columns_are_ignored(columns: ColumnMapping) -> None:
    table = make_table([[*VALID, "observação"]], header=[*make_table([]).columns, "Obs"])

    assert len(validate_rows(table, columns).valid) == 1


def test_missing_configured_column_is_fatal(columns: ColumnMapping) -> None:
    table = make_table(
        [["12/11/2026", "Boné", "1", "10"]], header=["Data", "Produto", "Qtd", "Valor"]
    )

    with pytest.raises(SchemaError) as info:
        check_schema(table, columns)

    message = str(info.value)
    assert "'Categoria'" in message
    assert "'Preço'" in message
    assert "'Vendedor'" in message
    assert "Colunas disponíveis" in message


def test_header_only_table_has_no_rows(columns: ColumnMapping) -> None:
    result = validate_rows(make_table([]), columns)

    assert result.total == 0
