import datetime as dt
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from fechou.config import ColumnMapping, ReportConfig
from fechou.domain.models import InvalidRow, ReportData, SaleRow, ValidationResult
from fechou.domain.period import Period
from fechou.pipeline import build_report_data

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"

HEADER = ["Data", "Produto", "Categoria", "Qtd", "Preço", "Vendedor"]

WEEK = Period(dt.date(2026, 11, 9), dt.date(2026, 11, 15))
NOW = dt.datetime(2026, 11, 16, 10, 30, tzinfo=dt.UTC)


def sale(
    day: dt.date,
    product: str,
    quantity: int,
    price: str,
    category: str | None = "Vestuário",
    seller: str | None = "Ana",
) -> SaleRow:
    return SaleRow(
        date=day,
        product=product,
        category=category,
        quantity=quantity,
        unit_price=Decimal(price),
        seller=seller,
    )


def make_report(
    rows: Sequence[SaleRow],
    invalid: Sequence[InvalidRow] = (),
    period: Period = WEEK,
    **report_options: object,
) -> ReportData:
    config = ReportConfig.model_validate({"business_name": "Loja Teste", **report_options})
    validation = ValidationResult(valid=tuple(rows), invalid=tuple(invalid))
    return build_report_data(validation, period, config, NOW)


@pytest.fixture
def sample_report() -> ReportData:
    rows = [
        sale(dt.date(2026, 11, 9), "Camiseta básica", 2, "49.90"),
        sale(dt.date(2026, 11, 11), "Calça jeans", 1, "1159.90", seller="Bruno"),
        sale(dt.date(2026, 11, 14), "Boné", 3, "44.90", category="Acessórios"),
        sale(dt.date(2026, 11, 3), "Boné", 1, "44.90", category="Acessórios"),  # previous week
    ]
    invalid = [
        InvalidRow(line=7, errors=("Qtd: deve ser um número inteiro maior que zero",)),
        InvalidRow(line=9, errors=("Preço: valor numérico inválido",), date=dt.date(2026, 11, 10)),
        # Outside both periods: must not appear in the report.
        InvalidRow(line=2, errors=("Produto: campo obrigatório vazio",), date=dt.date(2026, 9, 1)),
    ]
    return make_report(rows, invalid)


@pytest.fixture
def columns() -> ColumnMapping:
    return ColumnMapping(
        date="Data",
        product="Produto",
        category="Categoria",
        quantity="Qtd",
        unit_price="Preço",
        seller="Vendedor",
    )


def make_table(rows: list[list[str]], header: list[str] = HEADER) -> pd.DataFrame:
    """Build a RawTable the same way sources do: every cell is a string."""
    return pd.DataFrame(rows, columns=header, dtype=str)
