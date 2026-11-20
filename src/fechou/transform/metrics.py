"""Pure KPI calculations.

Money is aggregated as integer cents (``int64``) in pandas, so sums are exact,
and converted back to ``Decimal`` at the boundary. ``SaleRow.unit_price`` has
at most two decimal places (see ``domain/parsing.py``), so cents are exact.
"""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from fechou.domain.models import (
    DailyRevenue,
    PeriodMetrics,
    RankedItem,
    ReportMetrics,
    SaleRow,
)
from fechou.domain.period import Period

TOP_PRODUCTS = 5
UNCATEGORIZED = "Sem categoria"
NO_SELLER = "Sem vendedor"

_CENT = Decimal("0.01")
_RATIO = Decimal("0.0001")
_COLUMNS = ["date", "product", "category", "seller", "quantity", "cents"]


def _cents(value: Decimal) -> int:
    return int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _money(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(_CENT)


def _ratio(numerator: Decimal | int, denominator: Decimal | int) -> Decimal:
    return (Decimal(numerator) / Decimal(denominator)).quantize(_RATIO, rounding=ROUND_HALF_UP)


def percent_change(current: Decimal | int, previous: Decimal | int) -> Decimal | None:
    """Relative change as a fraction (``0.125`` = +12.5%); ``None`` when previous is 0."""
    if previous == 0:
        return None
    return _ratio(Decimal(current) - Decimal(previous), previous)


def to_frame(rows: Sequence[SaleRow]) -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            (
                row.date,
                row.product,
                row.category,
                row.seller,
                row.quantity,
                _cents(row.unit_price) * row.quantity,
            )
            for row in rows
        ],
        columns=_COLUMNS,
    )
    return frame.astype({"quantity": "int64", "cents": "int64"})


def _ranked(
    frame: pd.DataFrame,
    column: str,
    total_cents: int,
    *,
    fill: str | None = None,
    limit: int | None = None,
) -> tuple[RankedItem, ...]:
    """Group by ``column``; order by revenue desc, then name (deterministic ties)."""
    keys = frame[column]
    if fill is not None:
        if keys.isna().all():
            return ()  # the spreadsheet does not have this dimension
        keys = keys.fillna(fill)
    grouped = (
        frame.assign(_key=keys)
        .groupby("_key", sort=False)
        .agg(cents=("cents", "sum"), quantity=("quantity", "sum"), sales=("cents", "size"))
        .reset_index()
        .sort_values(["cents", "_key"], ascending=[False, True], kind="stable")
    )
    if limit is not None:
        grouped = grouped.head(limit)
    return tuple(
        RankedItem(
            name=str(name),
            revenue=_money(int(cents)),
            quantity=int(quantity),
            sales_count=int(sales),
            share=_ratio(int(cents), total_cents),
        )
        for name, cents, quantity, sales in grouped[
            ["_key", "cents", "quantity", "sales"]
        ].itertuples(index=False, name=None)
    )


def _daily(frame: pd.DataFrame, period: Period) -> tuple[DailyRevenue, ...]:
    per_day = frame.groupby("date").agg(cents=("cents", "sum"), sales=("cents", "size"))
    cents_by_day = {day: int(value) for day, value in per_day["cents"].items()}
    sales_by_day = {day: int(value) for day, value in per_day["sales"].items()}
    return tuple(
        DailyRevenue(
            date=day,
            revenue=_money(cents_by_day.get(day, 0)),
            sales_count=sales_by_day.get(day, 0),
        )
        for day in period
    )


def compute_period_metrics(rows: Sequence[SaleRow], period: Period) -> PeriodMetrics:
    """KPIs for the rows whose date falls inside ``period`` (others are ignored)."""
    frame = to_frame([row for row in rows if row.date in period])
    total_cents = int(frame["cents"].sum())
    sales_count = len(frame)
    daily = _daily(frame, period)
    has_sales = sales_count > 0

    return PeriodMetrics(
        period=period,
        revenue=_money(total_cents),
        sales_count=sales_count,
        items_sold=int(frame["quantity"].sum()),
        average_ticket=(
            (Decimal(total_cents) / 100 / sales_count).quantize(_CENT, rounding=ROUND_HALF_UP)
            if has_sales
            else None
        ),
        top_products=_ranked(frame, "product", total_cents, limit=TOP_PRODUCTS)
        if has_sales
        else (),
        by_category=_ranked(frame, "category", total_cents, fill=UNCATEGORIZED)
        if has_sales
        else (),
        by_seller=_ranked(frame, "seller", total_cents, fill=NO_SELLER) if has_sales else (),
        daily=daily,
        # max/min return the first day on ties, i.e. the earliest date.
        best_day=max(daily, key=lambda day: day.revenue) if has_sales else None,
        worst_day=min(daily, key=lambda day: day.revenue) if has_sales else None,
    )


def compute_report_metrics(rows: Sequence[SaleRow], period: Period) -> ReportMetrics:
    current = compute_period_metrics(rows, period)
    previous = compute_period_metrics(rows, period.previous())
    return ReportMetrics(
        current=current,
        previous=previous,
        revenue_change=percent_change(current.revenue, previous.revenue),
        sales_count_change=percent_change(current.sales_count, previous.sales_count),
    )
