"""Core domain models."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from fechou.domain import parsing
from fechou.domain.period import Period


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
    # The line's date when that cell itself is valid; lets the report show only
    # the problems that affect the periods being reported.
    date: dt.date | None = None

    def describe(self) -> str:
        return f"linha {self.line}: " + "; ".join(self.errors)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: tuple[SaleRow, ...]
    invalid: tuple[InvalidRow, ...]

    @property
    def total(self) -> int:
        return len(self.valid) + len(self.invalid)


# --- metrics --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RankedItem:
    """Revenue aggregated by a dimension (product, category or seller)."""

    name: str
    revenue: Decimal
    quantity: int
    sales_count: int
    share: Decimal  # fraction of the period revenue, 0..1 (4 decimal places)


@dataclass(frozen=True, slots=True)
class DailyRevenue:
    date: dt.date
    revenue: Decimal
    sales_count: int


@dataclass(frozen=True, slots=True)
class PeriodMetrics:
    period: Period
    revenue: Decimal
    sales_count: int
    items_sold: int
    average_ticket: Decimal | None  # None when there are no sales
    top_products: tuple[RankedItem, ...]
    by_category: tuple[RankedItem, ...]  # empty when the data has no categories
    by_seller: tuple[RankedItem, ...]  # empty when the data has no sellers
    daily: tuple[DailyRevenue, ...]  # every day of the period, zeros included
    best_day: DailyRevenue | None
    worst_day: DailyRevenue | None

    @property
    def is_empty(self) -> bool:
        return self.sales_count == 0


@dataclass(frozen=True, slots=True)
class ReportMetrics:
    """Current period, the immediately previous one and the variations."""

    current: PeriodMetrics
    previous: PeriodMetrics
    revenue_change: Decimal | None  # fraction (0.125 = +12,5%); None if previous is 0
    sales_count_change: Decimal | None


# --- report ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReportData:
    """Everything the renderers need; no formatting decisions here."""

    title: str
    business_name: str
    accent_color: str
    logo_uri: str | None
    generated_at: dt.datetime  # aware, in the report timezone
    metrics: ReportMetrics
    warnings: tuple[InvalidRow, ...]  # invalid lines relevant to the periods shown
    rows_read: int  # non-blank lines in the source
    rows_invalid: int  # all invalid lines in the source

    @property
    def period(self) -> Period:
        return self.metrics.current.period
