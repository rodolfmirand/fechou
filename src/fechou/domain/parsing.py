"""Pure parsers for spreadsheet cell values.

Every parser accepts the raw cell text and either returns a typed value or
raises ``ValueError`` with a pt-BR message meant for the report's warnings.
"""

import datetime as dt
import re
from decimal import Decimal, InvalidOperation

DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d")
MAX_DECIMAL_PLACES = 2

_INTEGER_RE = re.compile(r"^\d+$")
_DECIMAL_RE = re.compile(r"^-?\d+(\.\d+)?$")
_PREVIEW_LIMIT = 40


def preview(raw: str) -> str:
    """Quote a raw value for error messages, truncating long inputs."""
    text = raw if len(raw) <= _PREVIEW_LIMIT else raw[: _PREVIEW_LIMIT - 1] + "…"
    return f"'{text}'"


def parse_date(raw: str) -> dt.date:
    text = raw.strip()
    if not text:
        raise ValueError("campo obrigatório vazio")
    for fmt in DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt).date()  # noqa: DTZ007 - date only
        except ValueError:
            continue
    raise ValueError(f"data inválida {preview(raw)} (use dd/mm/aaaa ou aaaa-mm-dd)")


def parse_quantity(raw: str) -> int:
    text = raw.strip()
    if not text:
        raise ValueError("campo obrigatório vazio")
    if not _INTEGER_RE.match(text) or int(text) <= 0:
        raise ValueError(f"deve ser um número inteiro maior que zero (valor: {preview(raw)})")
    return int(text)


def _normalize_decimal(text: str) -> str:
    """Turn pt-BR or en-US formatted numbers into a plain ``1234.56`` string.

    Rules: with both separators, the rightmost one is the decimal separator;
    a lone comma is decimal; several dots (and no comma) are thousands.
    """
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            return text.replace(".", "").replace(",", ".")
        return text.replace(",", "")
    if "," in text:
        return text.replace(",", ".") if text.count(",") == 1 else text
    if text.count(".") > 1:
        return text.replace(".", "")
    return text


def parse_money(raw: str) -> Decimal:
    text = raw.strip().replace("R$", "").replace("\xa0", "").replace(" ", "")
    if not text:
        raise ValueError("campo obrigatório vazio")
    normalized = _normalize_decimal(text)
    if not _DECIMAL_RE.match(normalized):
        raise ValueError(f"valor numérico inválido {preview(raw)}")
    try:
        value = Decimal(normalized)
    except InvalidOperation as exc:  # pragma: no cover - guarded by the regex
        raise ValueError(f"valor numérico inválido {preview(raw)}") from exc
    if value < 0:
        raise ValueError(f"não pode ser negativo (valor: {preview(raw)})")
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > MAX_DECIMAL_PLACES:
        raise ValueError(
            f"mais de {MAX_DECIMAL_PLACES} casas decimais em {preview(raw)} "
            "(para milhar use 1.234,56)"
        )
    return value


def parse_required_text(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise ValueError("campo obrigatório vazio")
    return text


def parse_optional_text(raw: str) -> str | None:
    text = raw.strip()
    return text or None
