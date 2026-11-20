"""HTML and text rendering (no WeasyPrint needed)."""

import datetime as dt
from pathlib import Path

from fechou.domain.models import InvalidRow, ReportData
from fechou.render.pdf import (
    MAX_WARNINGS_IN_REPORT,
    build_day_bars,
    build_kpis,
    render_html,
    render_summary_text,
)
from tests.conftest import NOW, make_report, sale

NBSP = "\xa0"


def test_report_data_assembly(sample_report: ReportData) -> None:
    assert sample_report.period.start == dt.date(2026, 11, 9)
    assert sample_report.generated_at.utcoffset() == dt.timedelta(hours=-3)
    assert sample_report.generated_at == NOW
    assert sample_report.rows_read == 7
    assert sample_report.rows_invalid == 3
    # Only problems that may affect the shown periods (or with unknown date).
    assert [row.line for row in sample_report.warnings] == [7, 9]


def test_kpis(sample_report: ReportData) -> None:
    kpis = {kpi.label: kpi for kpi in build_kpis(sample_report)}

    assert kpis["Faturamento"].value == f"R${NBSP}1.394,40"
    assert kpis["Faturamento"].change == "+3.005,6%"
    assert kpis["Faturamento"].trend == "up"
    assert kpis["Vendas"].value == "3"
    assert kpis["Vendas"].change == "+200,0%"
    assert kpis["Ticket médio"].change is None
    assert kpis["Itens vendidos"].previous == "1"


def test_day_bars_are_relative_to_best_day(sample_report: ReportData) -> None:
    bars = build_day_bars(sample_report)

    assert len(bars) == 7
    assert [bar.height for bar in bars] == [8, 0, 100, 0, 0, 11, 0]
    assert [bar.is_best for bar in bars].index(True) == 2
    assert [bar.is_worst for bar in bars].index(True) == 1  # first zero day


def test_html_contains_key_sections(sample_report: ReportData) -> None:
    html = render_html(sample_report)

    assert "Loja Teste" in html
    assert "Relatório semanal de vendas" in html
    assert "09/11/2026 a 15/11/2026" in html
    assert "comparado com 02/11/2026 a 08/11/2026" in html
    assert f"R${NBSP}1.394,40" in html
    assert "Top 3 produtos por faturamento" in html
    assert "Por categoria" in html and "Por vendedor" in html
    assert "quarta-feira, 11/11/2026" in html
    assert "Avisos: 2 linha(s) descartada(s)" in html
    assert "linha 9: Preço: valor numérico inválido" in html
    assert "linha 2:" not in html
    assert "Sem movimento" not in html


def test_html_escapes_spreadsheet_content() -> None:
    report = make_report([sale(dt.date(2026, 11, 9), "<script>alert(1)</script>", 1, "10")])

    html = render_html(report)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_empty_period() -> None:
    report = make_report([sale(dt.date(2026, 11, 2), "Boné", 1, "10")])

    html = render_html(report)

    assert "Sem movimento no período." in html
    assert "Faturamento por dia" not in html
    assert "Top" not in html


def test_sections_without_category_or_seller_are_omitted() -> None:
    report = make_report([sale(dt.date(2026, 11, 9), "Boné", 1, "10", category=None, seller=None)])

    html = render_html(report)

    assert "Por categoria" not in html
    assert "Por vendedor" not in html


def test_only_category_section_when_no_sellers() -> None:
    report = make_report([sale(dt.date(2026, 11, 9), "Boné", 1, "10", seller=None)])

    html = render_html(report)

    assert "Por categoria" in html
    assert "Por vendedor" not in html


def test_many_warnings_are_truncated() -> None:
    invalid = [InvalidRow(line=n, errors=("Qtd: inválida",)) for n in range(2, 52)]
    report = make_report([sale(dt.date(2026, 11, 9), "Boné", 1, "10")], invalid)

    html = render_html(report)

    assert html.count("<li>") == MAX_WARNINGS_IN_REPORT
    assert "e mais 20 linha(s)" in html
    assert "Avisos: 50 linha(s)" in html


def test_branding_options(tmp_path: Path) -> None:
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"fake")
    report = make_report(
        [sale(dt.date(2026, 11, 9), "Boné", 1, "10")],
        accent_color="#aa3300",
        title="Fechamento",
        logo_path=str(logo),
    )

    html = render_html(report)

    assert "--accent: #aa3300" in html
    assert "<h1>Fechamento</h1>" in html
    assert logo.resolve().as_uri() in html


def test_summary_text(sample_report: ReportData) -> None:
    text = render_summary_text(sample_report)

    assert NBSP not in text
    assert text.splitlines()[:2] == [
        "Relatório semanal de vendas — Loja Teste",
        "Período: 09/11/2026 a 15/11/2026",
    ]
    assert "• Faturamento: R$ 1.394,40 (+3.005,6% vs. período anterior)" in text
    assert "• Ticket médio: R$ 464,80" in text
    assert "• Produto destaque: Calça jeans (R$ 1.159,90)" in text
    assert "• Melhor dia: quarta-feira, 11/11/2026 (R$ 1.159,90)" in text
    assert "• Dia mais fraco: terça-feira, 10/11/2026 (R$ 0,00)" in text
    assert "Atenção: 2 linha(s) descartada(s)" in text


def test_summary_text_empty_period() -> None:
    report = make_report([])

    text = render_summary_text(report)

    assert "Sem movimento no período." in text
    assert "Faturamento" not in text
