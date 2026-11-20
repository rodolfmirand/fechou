import datetime as dt
from decimal import Decimal

import pytest
from pydantic import ValidationError

from fechou.domain.models import InvalidRow, SaleRow


def test_sale_row_from_raw_strings() -> None:
    row = SaleRow.model_validate(
        {
            "date": "12/11/2026",
            "product": " Camiseta básica ",
            "category": "",
            "quantity": "3",
            "unit_price": "49,90",
            "seller": "Ana",
        }
    )

    assert row.date == dt.date(2026, 11, 12)
    assert row.product == "Camiseta básica"
    assert row.category is None
    assert row.quantity == 3
    assert row.unit_price == Decimal("49.90")
    assert row.total == Decimal("149.70")


def test_sale_row_from_typed_values() -> None:
    row = SaleRow(
        date=dt.date(2026, 11, 12),
        product="Boné",
        quantity=2,
        unit_price=Decimal("44.90"),
    )

    assert row.total == Decimal("89.80")
    assert row.seller is None


@pytest.mark.parametrize(
    ("field", "value"),
    [("quantity", 0), ("quantity", -2), ("unit_price", Decimal("-1"))],
)
def test_sale_row_rejects_invalid_typed_values(field: str, value: object) -> None:
    data: dict[str, object] = {
        "date": dt.date(2026, 11, 12),
        "product": "Boné",
        "quantity": 1,
        "unit_price": Decimal("1"),
    }
    data[field] = value

    with pytest.raises(ValidationError):
        SaleRow.model_validate(data)


def test_sale_row_reports_every_broken_field() -> None:
    with pytest.raises(ValidationError) as info:
        SaleRow.model_validate({"date": "x", "product": "", "quantity": "0", "unit_price": "abc"})

    assert {error["loc"][0] for error in info.value.errors()} == {
        "date",
        "product",
        "quantity",
        "unit_price",
    }


def test_sale_row_is_immutable() -> None:
    row = SaleRow(date=dt.date(2026, 1, 1), product="Boné", quantity=1, unit_price=Decimal(1))
    with pytest.raises(ValidationError):
        row.quantity = 5  # type: ignore[misc]


def test_invalid_row_description() -> None:
    row = InvalidRow(line=7, errors=("Qtd: inválida", "Preço: negativo"))
    assert row.describe() == "linha 7: Qtd: inválida; Preço: negativo"
