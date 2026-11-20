"""Report rendering: HTML (Jinja2) -> PDF (WeasyPrint), plus a plain-text summary.

WeasyPrint is imported lazily so commands that do not render (``validate``)
keep working on machines without the Pango system libraries.
"""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, PackageLoader, StrictUndefined

from fechou.domain.models import DailyRevenue, ReportData
from fechou.errors import FechouError
from fechou.render import formatting as fmt

MAX_WARNINGS_IN_REPORT = 30


class RenderError(FechouError):
    """The PDF could not be produced."""


@dataclass(frozen=True, slots=True)
class Kpi:
    """A headline indicator, already formatted for display."""

    label: str
    value: str
    change: str | None = None  # vs previous period; None = not compared
    trend: str = "none"
    previous: str | None = None


@dataclass(frozen=True, slots=True)
class DayBar:
    day: DailyRevenue
    height: int  # 0..100, relative to the best day
    is_best: bool
    is_worst: bool


def _environment() -> Environment:
    env = Environment(
        loader=PackageLoader("fechou.render", "templates"),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters.update(
        money=fmt.money,
        integer=fmt.integer,
        date=fmt.date,
        datetime=fmt.datetime,
        weekday=fmt.weekday,
        share=fmt.share,
        change=fmt.change,
    )
    return env


def build_kpis(report: ReportData) -> list[Kpi]:
    current, previous = report.metrics.current, report.metrics.previous
    revenue_change = report.metrics.revenue_change
    sales_change = report.metrics.sales_count_change
    return [
        Kpi(
            label="Faturamento",
            value=fmt.money(current.revenue),
            change=fmt.change(revenue_change),
            trend=fmt.trend(revenue_change),
            previous=fmt.money(previous.revenue),
        ),
        Kpi(
            label="Vendas",
            value=fmt.integer(current.sales_count),
            change=fmt.change(sales_change),
            trend=fmt.trend(sales_change),
            previous=fmt.integer(previous.sales_count),
        ),
        Kpi(
            label="Ticket médio",
            value=fmt.money(current.average_ticket),
            previous=fmt.money(previous.average_ticket),
        ),
        Kpi(
            label="Itens vendidos",
            value=fmt.integer(current.items_sold),
            previous=fmt.integer(previous.items_sold),
        ),
    ]


def build_day_bars(report: ReportData) -> list[DayBar]:
    current = report.metrics.current
    top = max((day.revenue for day in current.daily), default=Decimal(0))
    return [
        DayBar(
            day=day,
            height=int(day.revenue * 100 / top) if top else 0,
            is_best=current.best_day is not None and day.date == current.best_day.date,
            is_worst=current.worst_day is not None and day.date == current.worst_day.date,
        )
        for day in current.daily
    ]


def render_html(report: ReportData) -> str:
    template = _environment().get_template("report.html.j2")
    return template.render(
        report=report,
        current=report.metrics.current,
        previous=report.metrics.previous,
        kpis=build_kpis(report),
        day_bars=build_day_bars(report),
        warnings=report.warnings[:MAX_WARNINGS_IN_REPORT],
        hidden_warnings=max(0, len(report.warnings) - MAX_WARNINGS_IN_REPORT),
    )


def html_to_pdf(html: str, base_url: Path | None = None) -> bytes:
    try:
        from weasyprint import HTML  # lazy: needs native Pango libraries
    except OSError as exc:  # Pango/GObject DLLs not found
        raise RenderError(
            "Não foi possível carregar o WeasyPrint (bibliotecas Pango ausentes). "
            "Veja a seção 'Instalação do WeasyPrint' do README. "
            f"Detalhe: {exc}"
        ) from None
    document = HTML(string=html, base_url=str(base_url or Path.cwd()))
    pdf = document.write_pdf()
    if not isinstance(pdf, bytes):  # pragma: no cover - only when a target file is passed
        raise RenderError("O WeasyPrint não devolveu o PDF.")
    return pdf


def render_pdf(report: ReportData) -> bytes:
    return html_to_pdf(render_html(report))


def render_summary_text(report: ReportData) -> str:
    """Short plain-text summary (e-mail body, Telegram message, terminal)."""
    current = report.metrics.current
    lines = [
        f"{report.title} — {report.business_name}",
        f"Período: {fmt.period(report.period.start, report.period.end)}",
        "",
    ]
    if current.is_empty:
        lines.append("Sem movimento no período.")
    else:
        for kpi in build_kpis(report):
            suffix = f" ({kpi.change} vs. período anterior)" if kpi.change else ""
            lines.append(f"• {kpi.label}: {kpi.value}{suffix}")
        if current.top_products:
            best = current.top_products[0]
            lines.append(f"• Produto destaque: {best.name} ({fmt.money(best.revenue)})")
        if current.best_day is not None and current.worst_day is not None:
            lines.append(
                f"• Melhor dia: {fmt.weekday(current.best_day.date)}, "
                f"{fmt.date(current.best_day.date)} ({fmt.money(current.best_day.revenue)})"
            )
            lines.append(
                f"• Dia mais fraco: {fmt.weekday(current.worst_day.date)}, "
                f"{fmt.date(current.worst_day.date)} ({fmt.money(current.worst_day.revenue)})"
            )
    if report.warnings:
        lines += [
            "",
            f"Atenção: {len(report.warnings)} linha(s) descartada(s) por erro de preenchimento.",
        ]
    return "\n".join(lines).replace("\xa0", " ")
