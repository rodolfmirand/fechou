"""Regenerate the sample report shown in the README (fictional data, fixed date).

Usage:
    python scripts/generate_sample_report.py [--output docs/exemplo-relatorio.pdf]
"""

import argparse
import datetime as dt
import shutil
import tempfile
from pathlib import Path

from fechou.clock import FixedClock
from fechou.demo import run_demo

ROOT = Path(__file__).resolve().parent.parent
# A Monday morning in Sao Paulo, so the report covers 09-15/11/2026.
SAMPLE_INSTANT = dt.datetime(2026, 11, 16, 10, 0, tzinfo=dt.UTC)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera o PDF de exemplo do README.")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "exemplo-relatorio.pdf")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        result = run_demo(Path(tmp), FixedClock(SAMPLE_INSTANT))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(result.pdf_path, args.output)
    print(f"PDF de exemplo gravado em {args.output}")


if __name__ == "__main__":
    main()
