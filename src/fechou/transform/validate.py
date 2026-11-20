"""Schema and row validation (pure functions)."""

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from fechou.config import ColumnMapping
from fechou.domain.models import InvalidRow, SaleRow, ValidationResult
from fechou.errors import SchemaError
from fechou.extract.base import RawTable, line_number


def check_schema(table: RawTable, columns: ColumnMapping) -> None:
    """Fail fast when a configured column is missing from the spreadsheet."""
    available = [str(column) for column in table.columns]
    missing = [column for column in columns.mapped().values() if column not in available]
    if missing:
        raise SchemaError(
            "Colunas não encontradas na planilha: "
            + ", ".join(f"'{column}'" for column in missing)
            + ". Colunas disponíveis: "
            + (", ".join(f"'{column}'" for column in available) or "(nenhuma)")
            + ". Ajuste a seção 'columns' da configuração."
        )


def _error_message(error: ErrorDetails, labels: dict[str, str]) -> str:
    field = str(error["loc"][0]) if error["loc"] else ""
    label = labels.get(field, field)
    if error["type"] == "value_error":
        message = str(error.get("ctx", {}).get("error", error["msg"]))
    else:
        message = error["msg"]
    return f"{label}: {message}"


def validate_rows(table: RawTable, columns: ColumnMapping) -> ValidationResult:
    """Split the raw table into valid ``SaleRow``s and described invalid lines.

    Fully blank lines are ignored and not counted.
    """
    check_schema(table, columns)
    mapping = columns.mapped()  # internal field -> header
    fields = list(mapping)
    headers = [mapping[field] for field in fields]

    valid: list[SaleRow] = []
    invalid: list[InvalidRow] = []
    for row_index, *cells in table[headers].itertuples(index=True, name=None):
        values = [str(cell) for cell in cells]
        if all(not value.strip() for value in values):
            continue
        try:
            valid.append(SaleRow.model_validate(dict(zip(fields, values, strict=True))))
        except ValidationError as exc:
            invalid.append(
                InvalidRow(
                    line=line_number(int(row_index)),
                    errors=tuple(_error_message(error, mapping) for error in exc.errors()),
                )
            )
    return ValidationResult(valid=tuple(valid), invalid=tuple(invalid))
