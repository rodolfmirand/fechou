"""``fechou demo``: fictional data -> CSV -> validation -> metrics -> PDF, no delivery.

It goes through the same CSV source, validator and renderer as a real run,
so the demo exercises the production path rather than a shortcut.
"""

from dataclasses import dataclass
from pathlib import Path

from fechou.clock import Clock
from fechou.config import ColumnMapping, ReportConfig
from fechou.demo_data import DEMO_COLUMNS, generate_sales, write_csv
from fechou.domain.models import ReportData
from fechou.domain.period import previous_full_week
from fechou.errors import FechouError
from fechou.extract.csv_source import CsvSource
from fechou.pipeline import build_report_data, report_filename
from fechou.render.pdf import render_pdf
from fechou.transform.validate import validate_rows

DEMO_SOURCE_ID = "loja-demo"
DEMO_SEED = 2026
DEMO_INVALID_ROWS = 4


@dataclass(frozen=True, slots=True)
class DemoOutput:
    report: ReportData
    csv_path: Path
    pdf_path: Path


def demo_report_config() -> ReportConfig:
    return ReportConfig(
        title="Relatório semanal de vendas",
        business_name="Loja Demo (dados fictícios)",
    )


def run_demo(output_dir: Path, clock: Clock) -> DemoOutput:
    config = demo_report_config()
    now = clock.now()
    period = previous_full_week(now, config.zone)
    previous = period.previous()

    rows = generate_sales(
        previous.start, period.end, seed=DEMO_SEED, invalid_rows=DEMO_INVALID_ROWS
    )
    stem = report_filename(DEMO_SOURCE_ID, period)
    csv_path = output_dir / f"{stem}.csv"
    pdf_path = output_dir / f"{stem}.pdf"
    try:
        write_csv(rows, csv_path)
    except OSError as exc:
        raise FechouError(f"Não foi possível gravar em {output_dir}: {exc.strerror}") from None

    validation = validate_rows(
        CsvSource(DEMO_SOURCE_ID, csv_path).read(),
        ColumnMapping.model_validate(DEMO_COLUMNS),
    )
    report = build_report_data(validation, period, config, now)
    pdf = render_pdf(report)
    try:
        pdf_path.write_bytes(pdf)
    except OSError as exc:
        raise FechouError(f"Não foi possível gravar {pdf_path}: {exc.strerror}") from None
    return DemoOutput(report=report, csv_path=csv_path, pdf_path=pdf_path)
