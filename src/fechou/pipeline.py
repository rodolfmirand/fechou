"""Glue between the pipeline steps (validated rows -> report data)."""

import datetime as dt

from fechou.config import ReportConfig
from fechou.domain.models import ReportData, ValidationResult
from fechou.domain.period import Period
from fechou.transform.metrics import compute_report_metrics
from fechou.transform.validate import relevant_invalid_rows


def report_filename(source_id: str, period: Period) -> str:
    """File stem for a report: ``fechou_<source>_<start>_<end>``."""
    return f"fechou_{source_id}_{period.start.isoformat()}_{period.end.isoformat()}"


def build_report_data(
    validation: ValidationResult,
    period: Period,
    report: ReportConfig,
    now: dt.datetime,
) -> ReportData:
    metrics = compute_report_metrics(validation.valid, period)
    return ReportData(
        title=report.title,
        business_name=report.business_name,
        accent_color=report.accent_color,
        logo_uri=report.logo_path.resolve().as_uri() if report.logo_path else None,
        generated_at=now.astimezone(report.zone),
        metrics=metrics,
        warnings=relevant_invalid_rows(
            validation.invalid, [metrics.current.period, metrics.previous.period]
        ),
        rows_read=validation.total,
        rows_invalid=len(validation.invalid),
    )
