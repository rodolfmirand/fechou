import datetime as dt
from decimal import Decimal

import pytest

from fechou.render import formatting as fmt

NBSP = "\xa0"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1234.56"), f"R${NBSP}1.234,56"),
        (Decimal("0"), f"R${NBSP}0,00"),
        (Decimal("49.9"), f"R${NBSP}49,90"),
        (Decimal("1234567.8"), f"R${NBSP}1.234.567,80"),
        (None, "—"),
    ],
)
def test_money(value: Decimal | None, expected: str) -> None:
    assert fmt.money(value) == expected


def test_integer_uses_dot_for_thousands() -> None:
    assert fmt.integer(12345) == "12.345"
    assert fmt.integer(7) == "7"


def test_dates() -> None:
    day = dt.date(2026, 11, 14)

    assert fmt.date(day) == "14/11/2026"
    assert fmt.date(dt.date(2027, 1, 3)) == "03/01/2027"
    assert fmt.weekday(day) == "sábado"
    assert fmt.weekday(day, short=True) == "sáb."
    assert fmt.period(dt.date(2026, 11, 9), dt.date(2026, 11, 15)) == "09/11/2026 a 15/11/2026"


def test_datetime() -> None:
    value = dt.datetime(2026, 11, 16, 7, 5, tzinfo=dt.UTC)
    assert fmt.datetime(value) == "16/11/2026 07:05"


@pytest.mark.parametrize(
    ("value", "expected", "trend"),
    [
        (Decimal("0.125"), "+12,5%", "up"),
        (Decimal("-0.0321"), "-3,2%", "down"),
        (Decimal("1.5"), "+150,0%", "up"),
        (Decimal("12.3456"), "+1.234,6%", "up"),
        (Decimal("0"), "0,0%", "flat"),
        # Rounds to zero: no misleading sign.
        (Decimal("0.0004"), "0,0%", "flat"),
        (Decimal("-0.0004"), "0,0%", "flat"),
        (None, "—", "none"),
    ],
)
def test_change_and_trend(value: Decimal | None, expected: str, trend: str) -> None:
    assert fmt.change(value) == expected
    assert fmt.trend(value) == trend


def test_share_has_no_sign() -> None:
    assert fmt.share(Decimal("0.5814")) == "58,1%"
    assert fmt.share(Decimal("1")) == "100,0%"
