"""Regenerate ``examples/vendas_demo.csv`` with fictional, deterministic data.

Usage:
    python scripts/generate_demo_data.py [--start 2026-09-07] [--end 2026-11-15]
                                         [--seed 42] [--invalid 6]
                                         [--output examples/vendas_demo.csv]
"""

import argparse
import datetime as dt
from pathlib import Path

from fechou.demo_data import generate_sales, write_csv

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera dados fictícios de vendas em CSV.")
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2026, 9, 7))
    parser.add_argument("--end", type=dt.date.fromisoformat, default=dt.date(2026, 11, 15))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--invalid", type=int, default=6, help="linhas inválidas propositais")
    parser.add_argument("--output", type=Path, default=ROOT / "examples" / "vendas_demo.csv")
    args = parser.parse_args()

    rows = generate_sales(args.start, args.end, seed=args.seed, invalid_rows=args.invalid)
    write_csv(rows, args.output)
    print(f"{len(rows)} linhas gravadas em {args.output}")


if __name__ == "__main__":
    main()
