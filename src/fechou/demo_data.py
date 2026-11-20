"""Deterministic fictional sales data for demo mode and examples.

All names, products and values are made up. Output uses the same headers as
``examples/config.example.yaml`` and mixes pt-BR and ISO formats on purpose,
so the validator's normalization is exercised by the demo itself.
"""

import csv
import datetime as dt
import random
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path

DEMO_COLUMNS: dict[str, str] = {
    "date": "Data",
    "product": "Produto",
    "category": "Categoria",
    "quantity": "Qtd",
    "unit_price": "Preço",
    "seller": "Vendedor",
}

# (product, category, unit price)
CATALOG: tuple[tuple[str, str, Decimal], ...] = (
    ("Camiseta básica", "Vestuário", Decimal("49.90")),
    ("Camiseta estampada", "Vestuário", Decimal("69.90")),
    ("Calça jeans", "Vestuário", Decimal("159.90")),
    ("Bermuda de sarja", "Vestuário", Decimal("89.90")),
    ("Moletom com capuz", "Vestuário", Decimal("189.90")),
    ("Vestido midi", "Vestuário", Decimal("139.90")),
    ("Tênis casual", "Calçados", Decimal("249.90")),
    ("Sandália rasteira", "Calçados", Decimal("79.90")),
    ("Chinelo", "Calçados", Decimal("34.90")),
    ("Boné", "Acessórios", Decimal("44.90")),
    ("Cinto de couro", "Acessórios", Decimal("74.90")),
    ("Meia (kit com 3)", "Acessórios", Decimal("29.90")),
    ("Mochila", "Acessórios", Decimal("199.90")),
    ("Óculos de sol", "Acessórios", Decimal("119.90")),
)

SELLERS: tuple[str, ...] = ("Ana", "Bruno", "Carla", "Diego")

# Average number of sales per weekday (Monday=0 ... Sunday=6).
_DAILY_SALES = (8, 9, 10, 11, 15, 18, 6)

# Each entry overrides some cells of a valid row to make it invalid.
_INVALID_PATCHES: tuple[dict[str, str], ...] = (
    {"product": ""},
    {"quantity": "0"},
    {"unit_price": "abc"},
    {"date": "31/02/2026"},
    {"unit_price": "-10,00"},
    {"quantity": "2,5"},
)


def _format_price(value: Decimal, rng: random.Random) -> str:
    text = f"{value:.2f}"
    # Most rows use the pt-BR decimal comma; some keep the dot.
    return text.replace(".", ",") if rng.random() < 0.8 else text


def _format_date(value: dt.date, rng: random.Random) -> str:
    return value.strftime("%d/%m/%Y") if rng.random() < 0.85 else value.isoformat()


def generate_sales(
    start: dt.date,
    end: dt.date,
    *,
    seed: int = 42,
    invalid_rows: int = 0,
) -> list[dict[str, str]]:
    """Return rows keyed by internal field names, every cell as text.

    ``invalid_rows`` valid rows are replaced by broken ones (cycling through
    a fixed set of problems) at deterministic positions.
    """
    if end < start:
        raise ValueError("end must not be before start")
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    day = start
    while day <= end:
        base = _DAILY_SALES[day.weekday()]
        for _ in range(max(1, base + rng.randint(-3, 3))):
            product, category, price = rng.choice(CATALOG)
            rows.append(
                {
                    "date": _format_date(day, rng),
                    "product": product,
                    "category": category,
                    "quantity": str(rng.choices((1, 2, 3, 4, 5), weights=(55, 25, 10, 6, 4))[0]),
                    "unit_price": _format_price(price, rng),
                    "seller": rng.choice(SELLERS),
                }
            )
        day += dt.timedelta(days=1)

    if invalid_rows:
        positions = sorted(rng.sample(range(len(rows)), k=min(invalid_rows, len(rows))))
        for n, position in enumerate(positions):
            rows[position] = {**rows[position], **_INVALID_PATCHES[n % len(_INVALID_PATCHES)]}
    return rows


def write_csv(
    rows: Iterable[dict[str, str]],
    path: Path,
    *,
    columns: dict[str, str] = DEMO_COLUMNS,
    delimiter: str = ",",
) -> None:
    """Write rows (keyed by internal names) using the spreadsheet headers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=delimiter, lineterminator="\n")
        writer.writerow(columns.values())
        for row in rows:
            writer.writerow(row.get(field, "") for field in columns)
