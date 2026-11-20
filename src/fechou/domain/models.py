"""Core domain models."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from fechou.domain import parsing


class SaleRow(BaseModel):
    """One valid sale line, already normalized.

    Accepts raw spreadsheet strings (pt-BR or ISO formats) as well as typed
    values, so the same model serves the CSV/Sheets path and the tests.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    date: dt.date
    product: str
    category: str | None = None
    quantity: int
    unit_price: Decimal
    seller: str | None = None

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity

    @field_validator("date", mode="before")
    @classmethod
    def _parse_date(cls, value: Any) -> Any:
        return parsing.parse_date(value) if isinstance(value, str) else value

    @field_validator("product", mode="before")
    @classmethod
    def _parse_product(cls, value: Any) -> Any:
        return parsing.parse_required_text(value) if isinstance(value, str) else value

    @field_validator("category", "seller", mode="before")
    @classmethod
    def _parse_optional_text(cls, value: Any) -> Any:
        return parsing.parse_optional_text(value) if isinstance(value, str) else value

    @field_validator("quantity", mode="before")
    @classmethod
    def _parse_quantity(cls, value: Any) -> Any:
        if isinstance(value, str):
            return parsing.parse_quantity(value)
        if isinstance(value, int) and not isinstance(value, bool) and value <= 0:
            raise ValueError(f"deve ser um número inteiro maior que zero (valor: {value})")
        return value

    @field_validator("unit_price", mode="before")
    @classmethod
    def _parse_unit_price(cls, value: Any) -> Any:
        if isinstance(value, str):
            return parsing.parse_money(value)
        if isinstance(value, int | float | Decimal) and value < 0:
            raise ValueError(f"não pode ser negativo (valor: {value})")
        return value


@dataclass(frozen=True, slots=True)
class InvalidRow:
    """A discarded spreadsheet line and the reasons, in pt-BR."""

    line: int
    errors: tuple[str, ...]

    def describe(self) -> str:
        return f"linha {self.line}: " + "; ".join(self.errors)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: tuple[SaleRow, ...]
    invalid: tuple[InvalidRow, ...]

    @property
    def total(self) -> int:
        return len(self.valid) + len(self.invalid)
