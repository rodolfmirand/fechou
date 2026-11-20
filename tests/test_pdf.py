"""PDF "golden" tests: never compare bytes; check pages and key texts (pypdf).

Skipped automatically when WeasyPrint's native libraries (Pango) are missing.
"""

import datetime as dt
import io
import os
import re
from pathlib import Path

import pytest
from pypdf import PdfReader
from typer.testing import CliRunner

from fechou import cli
from fechou.clock import FixedClock
from fechou.demo import run_demo
from fechou.domain.models import ReportData
from fechou.render.pdf import render_pdf
from tests.conftest import make_report

try:
    import weasyprint  # noqa: F401
except OSError:  # pragma: no cover - depends on the machine
    if os.environ.get("FECHOU_REQUIRE_PDF") == "1":  # CI must not skip silently
        raise
    pytest.skip("WeasyPrint native libraries (Pango) not available", allow_module_level=True)

CLOCK = FixedClock(dt.datetime(2026, 11, 16, 10, 0, tzinfo=dt.UTC))


def pdf_text(pdf: bytes) -> tuple[int, str]:
    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join(page.extract_text() for page in reader.pages)
    # Normalize NBSP and runs of whitespace introduced by text extraction.
    return len(reader.pages), re.sub(r"\s+", " ", text.replace("\xa0", " "))


def test_report_pdf_has_pages_and_key_texts(sample_report: ReportData) -> None:
    pdf = render_pdf(sample_report)

    assert pdf.startswith(b"%PDF-")
    pages, text = pdf_text(pdf)
    assert pages == 1
    for expected in (
        "LOJA TESTE",  # uppercased by CSS text-transform
        "Relatório semanal de vendas",
        "09/11/2026 a 15/11/2026",
        "Faturamento por dia",
        "R$ 1.394,40",
        "+3.005,6%",
        "Calça jeans",
        "Avisos: 2 linha(s) descartada(s)",
        "Página 1 de 1",
    ):
        assert expected in text, expected


def test_empty_period_pdf() -> None:
    pages, text = pdf_text(render_pdf(make_report([])))

    assert pages == 1
    assert "Sem movimento no período." in text


def test_run_demo_writes_csv_and_pdf(tmp_path: Path) -> None:
    result = run_demo(tmp_path / "out", CLOCK)

    assert result.report.period.start == dt.date(2026, 11, 9)
    assert result.csv_path.name == "fechou_loja-demo_2026-11-09_2026-11-15.csv"
    assert result.csv_path.exists()
    assert result.pdf_path.name == "fechou_loja-demo_2026-11-09_2026-11-15.pdf"
    assert result.report.rows_invalid == 4
    assert not result.report.metrics.current.is_empty
    assert not result.report.metrics.previous.is_empty

    pages, text = pdf_text(result.pdf_path.read_bytes())
    assert pages >= 1
    assert "LOJA DEMO (DADOS FICTÍCIOS)" in text  # CSS text-transform
    assert "Avisos: 4 linha(s)" in text


def test_demo_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "SystemClock", lambda: CLOCK)

    result = CliRunner().invoke(cli.app, ["demo", "--output", str(tmp_path)])

    assert result.exit_code == cli.EXIT_OK, result.output
    assert "Período: 09/11/2026 a 15/11/2026" in result.stdout
    assert "Modo demo: nada foi enviado." in result.stdout
    assert len(list(tmp_path.glob("*.pdf"))) == 1
