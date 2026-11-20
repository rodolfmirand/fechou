"""pt-BR formatting helpers (Babel). Used as Jinja2 filters and in text summaries."""

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from babel.dates import format_date as _babel_date
from babel.numbers import format_currency, format_decimal

LOCALE = "pt_BR"
EMPTY = "—"

_PERMILLE = Decimal("0.001")  # one decimal place in percent


def money(value: Decimal | None) -> str:
    """``R$ 1.234,56`` (with a non-breaking space, as CLDR defines)."""
    if value is None:
        return EMPTY
    return format_currency(value, "BRL", locale=LOCALE)


def integer(value: int) -> str:
    return format_decimal(value, locale=LOCALE)


def date(value: dt.date) -> str:
    return _babel_date(value, "dd/MM/yyyy", locale=LOCALE)


def datetime(value: dt.datetime) -> str:
    return f"{date(value)} {value:%H:%M}"


def weekday(value: dt.date, *, short: bool = False) -> str:
    return _babel_date(value, "EEE" if short else "EEEE", locale=LOCALE)


def share(value: Decimal) -> str:
    """A 0..1 fraction as ``58,1%``."""
    return _percent(value, signed=False)


def change(value: Decimal | None) -> str:
    """A relative change as ``+12,5%`` / ``-3,2%`` / ``0,0%``; ``—`` when unknown."""
    if value is None:
        return EMPTY
    return _percent(value, signed=True)


def _percent(value: Decimal, *, signed: bool) -> str:
    rounded = value.quantize(_PERMILLE, rounding=ROUND_HALF_UP)
    text = format_decimal(abs(rounded) * 100, format="#,##0.0", locale=LOCALE) + "%"
    if signed and rounded > 0:
        return "+" + text
    if rounded < 0:
        return "-" + text
    return text


def trend(value: Decimal | None) -> str:
    """CSS-friendly direction of a change: ``up``, ``down``, ``flat`` or ``none``."""
    if value is None:
        return "none"
    rounded = value.quantize(_PERMILLE, rounding=ROUND_HALF_UP)
    return "up" if rounded > 0 else "down" if rounded < 0 else "flat"


def period(start: dt.date, end: dt.date) -> str:
    return f"{date(start)} a {date(end)}"
