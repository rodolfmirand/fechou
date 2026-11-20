import datetime as dt
from decimal import Decimal

import pytest

from fechou.domain.models import SaleRow
from fechou.domain.period import Period
from fechou.transform.metrics import (
    NO_SELLER,
    UNCATEGORIZED,
    compute_period_metrics,
    compute_report_metrics,
    percent_change,
)

WEEK = Period(dt.date(2026, 11, 9), dt.date(2026, 11, 15))  # Mon..Sun
D = Decimal


def sale(
    day: int,
    product: str,
    quantity: int,
    price: str,
    category: str | None = "Vestuário",
    seller: str | None = "Ana",
    month: int = 11,
) -> SaleRow:
    return SaleRow(
        date=dt.date(2026, month, day),
        product=product,
        category=category,
        quantity=quantity,
        unit_price=D(price),
        seller=seller,
    )


ROWS = [
    sale(9, "Camiseta", 2, "49.90"),  # 99.80
    sale(9, "Boné", 1, "44.90", category="Acessórios", seller="Bruno"),  # 44.90
    sale(11, "Calça", 1, "159.90", seller="Bruno"),  # 159.90
    sale(13, "Camiseta", 3, "49.90", seller=None),  # 149.70
    sale(14, "Tênis", 1, "249.90", category=None),  # 249.90
    # Outside the week: must be ignored.
    sale(8, "Tênis", 10, "249.90"),
    sale(16, "Tênis", 10, "249.90"),
]


class TestPeriodMetrics:
    def test_totals_and_ticket(self) -> None:
        metrics = compute_period_metrics(ROWS, WEEK)

        assert metrics.revenue == D("704.20")
        assert metrics.sales_count == 5
        assert metrics.items_sold == 8
        assert metrics.average_ticket == D("140.84")
        assert not metrics.is_empty

    def test_average_ticket_is_rounded_half_up_to_cents(self) -> None:
        rows = [sale(9, "A", 1, "10.00"), sale(9, "B", 1, "10.00"), sale(9, "C", 1, "10.01")]
        # 30.01 / 3 = 10.00333...
        assert compute_period_metrics(rows, WEEK).average_ticket == D("10.00")
        rows = [sale(9, "A", 1, "0.01"), sale(9, "B", 1, "0.00")]
        # 0.01 / 2 = 0.005 -> 0.01
        assert compute_period_metrics(rows, WEEK).average_ticket == D("0.01")

    def test_money_sums_are_exact(self) -> None:
        # As floats, 0.1 * 3 would be 0.30000000000000004.
        rows = [sale(9, "Bala", 1, "0.10") for _ in range(3)]
        assert compute_period_metrics(rows, WEEK).revenue == D("0.30")

    def test_top_products_by_revenue(self) -> None:
        top = compute_period_metrics(ROWS, WEEK).top_products

        # Ranked by revenue, not quantity: 1 Tênis (249.90) beats 5 Camisetas (249.50).
        assert [(item.name, item.revenue, item.quantity, item.sales_count) for item in top] == [
            ("Tênis", D("249.90"), 1, 1),
            ("Camiseta", D("249.50"), 5, 2),
            ("Calça", D("159.90"), 1, 1),
            ("Boné", D("44.90"), 1, 1),
        ]

    def test_top_products_limited_to_five_with_name_tiebreak(self) -> None:
        rows = [sale(10, name, 1, "10.00") for name in "GFEDCBA"]

        top = compute_period_metrics(rows, WEEK).top_products

        assert [item.name for item in top] == ["A", "B", "C", "D", "E"]

    def test_by_category_with_missing_values(self) -> None:
        by_category = compute_period_metrics(ROWS, WEEK).by_category

        assert [(item.name, item.revenue) for item in by_category] == [
            ("Vestuário", D("409.40")),
            (UNCATEGORIZED, D("249.90")),
            ("Acessórios", D("44.90")),
        ]
        assert sum(item.share for item in by_category) == pytest.approx(1, abs=D("0.0003"))
        assert by_category[0].share == D("0.5814")

    def test_by_seller_with_missing_values(self) -> None:
        by_seller = compute_period_metrics(ROWS, WEEK).by_seller

        assert [(item.name, item.revenue) for item in by_seller] == [
            ("Ana", D("349.70")),
            ("Bruno", D("204.80")),
            (NO_SELLER, D("149.70")),
        ]

    def test_dimensions_absent_from_the_data_are_empty(self) -> None:
        rows = [sale(9, "A", 1, "10.00", category=None, seller=None)]

        metrics = compute_period_metrics(rows, WEEK)

        assert metrics.by_category == ()
        assert metrics.by_seller == ()

    def test_daily_includes_every_day_and_best_worst(self) -> None:
        metrics = compute_period_metrics(ROWS, WEEK)

        assert [day.date for day in metrics.daily] == list(WEEK)
        assert [day.revenue for day in metrics.daily] == [
            D("144.70"),
            D("0.00"),
            D("159.90"),
            D("0.00"),
            D("149.70"),
            D("249.90"),
            D("0.00"),
        ]
        assert metrics.best_day is not None
        assert metrics.best_day.date == dt.date(2026, 11, 14)
        assert metrics.worst_day is not None
        # Days without sales count; ties resolve to the earliest date.
        assert metrics.worst_day.date == dt.date(2026, 11, 10)
        assert metrics.worst_day.sales_count == 0

    def test_empty_period(self) -> None:
        metrics = compute_period_metrics([], WEEK)

        assert metrics.is_empty
        assert metrics.revenue == D("0.00")
        assert metrics.items_sold == 0
        assert metrics.average_ticket is None
        assert metrics.top_products == ()
        assert metrics.by_category == ()
        assert metrics.best_day is None
        assert metrics.worst_day is None
        assert len(metrics.daily) == 7


class TestPercentChange:
    @pytest.mark.parametrize(
        ("current", "previous", "expected"),
        [
            (D("112.50"), D("100.00"), D("0.1250")),
            (D("50"), D("100"), D("-0.5000")),
            (D("0"), D("100"), D("-1.0000")),
            (D("100"), D("100"), D("0.0000")),
            (2, 3, D("-0.3333")),
            (D("100"), D("0"), None),
            (D("0.00"), D("0.00"), None),
            (5, 0, None),
        ],
    )
    def test_values(
        self, current: Decimal | int, previous: Decimal | int, expected: Decimal | None
    ) -> None:
        assert percent_change(current, previous) == expected


class TestReportMetrics:
    def test_compares_with_previous_week(self) -> None:
        rows = [
            *ROWS,
            sale(3, "Camiseta", 1, "49.90"),  # previous week (2-8 Nov)
            sale(5, "Boné", 4, "44.90"),
        ]

        report = compute_report_metrics(rows, WEEK)

        assert report.previous.period == Period(dt.date(2026, 11, 2), dt.date(2026, 11, 8))
        # Previous: 49.90 + 179.60 + 2499.00 (the 10 Tênis on the 8th) = 2728.50
        assert report.previous.revenue == D("2728.50")
        assert report.previous.sales_count == 3
        assert report.revenue_change == D("-0.7419")  # (704.20 - 2728.50) / 2728.50
        assert report.sales_count_change == D("0.6667")

    def test_previous_without_sales_gives_none(self) -> None:
        rows = [sale(9, "A", 1, "10.00")]

        report = compute_report_metrics(rows, WEEK)

        assert report.previous.is_empty
        assert report.revenue_change is None
        assert report.sales_count_change is None
