import datetime as dt
from decimal import Decimal

import pytest

from fechou.domain import parsing


class TestParseDate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("12/11/2026", dt.date(2026, 11, 12)),
            ("2026-11-12", dt.date(2026, 11, 12)),
            (" 01/01/2027 ", dt.date(2027, 1, 1)),
            ("29/02/2028", dt.date(2028, 2, 29)),
        ],
    )
    def test_accepts_br_and_iso_formats(self, raw: str, expected: dt.date) -> None:
        assert parsing.parse_date(raw) == expected

    @pytest.mark.parametrize("raw", ["31/02/2026", "2026/11/12", "12-11-2026", "ontem", "11/12/26"])
    def test_rejects_other_formats_and_impossible_dates(self, raw: str) -> None:
        with pytest.raises(ValueError, match="data inválida"):
            parsing.parse_date(raw)

    @pytest.mark.parametrize("raw", ["", "   "])
    def test_rejects_empty(self, raw: str) -> None:
        with pytest.raises(ValueError, match="obrigatório"):
            parsing.parse_date(raw)


class TestParseQuantity:
    @pytest.mark.parametrize(("raw", "expected"), [("1", 1), (" 3 ", 3), ("120", 120)])
    def test_accepts_positive_integers(self, raw: str, expected: int) -> None:
        assert parsing.parse_quantity(raw) == expected

    @pytest.mark.parametrize("raw", ["0", "-1", "2,5", "2.5", "três", "1e3"])
    def test_rejects_non_positive_or_non_integer(self, raw: str) -> None:
        with pytest.raises(ValueError, match="inteiro maior que zero"):
            parsing.parse_quantity(raw)

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="obrigatório"):
            parsing.parse_quantity("")


class TestParseMoney:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("49.90", Decimal("49.90")),
            ("49,90", Decimal("49.90")),
            ("49,9", Decimal("49.9")),
            ("0", Decimal("0")),
            ("1234", Decimal("1234")),
            ("1.234,56", Decimal("1234.56")),
            ("1,234.56", Decimal("1234.56")),
            ("1.234.567,89", Decimal("1234567.89")),
            ("1.234.567", Decimal("1234567")),
            ("R$ 1.234,56", Decimal("1234.56")),
            ("R$\xa049,90", Decimal("49.90")),
        ],
    )
    def test_accepts_br_and_us_formats(self, raw: str, expected: Decimal) -> None:
        assert parsing.parse_money(raw) == expected

    @pytest.mark.parametrize("raw", ["abc", "12,34,56", "1.2.3,4,5", "--1", "R$"])
    def test_rejects_non_numeric(self, raw: str) -> None:
        with pytest.raises(ValueError):
            parsing.parse_money(raw)

    def test_rejects_negative(self) -> None:
        with pytest.raises(ValueError, match="negativo"):
            parsing.parse_money("-10,00")

    @pytest.mark.parametrize("raw", ["1.234", "1,234", "49,999"])
    def test_rejects_more_than_two_decimals_as_ambiguous(self, raw: str) -> None:
        # "1.234" could be 1234 (pt-BR thousands) or 1.234: flag it instead of guessing.
        with pytest.raises(ValueError, match="casas decimais"):
            parsing.parse_money(raw)

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="obrigatório"):
            parsing.parse_money("  ")


class TestText:
    def test_required_text_is_trimmed(self) -> None:
        assert parsing.parse_required_text("  Boné ") == "Boné"

    def test_required_text_rejects_blank(self) -> None:
        with pytest.raises(ValueError, match="obrigatório"):
            parsing.parse_required_text("   ")

    @pytest.mark.parametrize(("raw", "expected"), [("", None), ("  ", None), (" Ana ", "Ana")])
    def test_optional_text(self, raw: str, expected: str | None) -> None:
        assert parsing.parse_optional_text(raw) == expected


def test_preview_truncates_long_values() -> None:
    shown = parsing.preview("x" * 100)
    assert len(shown) == 42  # 40 chars + quotes
    assert shown.endswith("…'")
