from pathlib import Path

import pandas as pd
import pytest

from fechou.config import ColumnMapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"

HEADER = ["Data", "Produto", "Categoria", "Qtd", "Preço", "Vendedor"]


@pytest.fixture
def columns() -> ColumnMapping:
    return ColumnMapping(
        date="Data",
        product="Produto",
        category="Categoria",
        quantity="Qtd",
        unit_price="Preço",
        seller="Vendedor",
    )


def make_table(rows: list[list[str]], header: list[str] = HEADER) -> pd.DataFrame:
    """Build a RawTable the same way sources do: every cell is a string."""
    return pd.DataFrame(rows, columns=header, dtype=str)
