"""``fechou run``: the scheduled pipeline (section 8.1 of PROJETO.md).

period -> idempotency check -> extract -> validate -> metrics -> PDF -> deliver
-> record. Every dependency (clock, store, delivery channels, sleep) is
injected, so the whole flow is tested without network or real time.
"""

import datetime as dt
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from fechou.clock import Clock
from fechou.config import AppConfig
from fechou.deliver.base import Delivery, DeliveryError, ReportMessage, send_with_retries
from fechou.deliver.smtp import SmtpDelivery
from fechou.domain.period import Period, resolve_period
from fechou.errors import ConfigError, FechouError
from fechou.extract import build_source
from fechou.logging_setup import get_logger
from fechou.pipeline import build_report_data, report_filename
from fechou.render import formatting as fmt
from fechou.render.pdf import render_pdf, render_summary_text
from fechou.settings import Settings, require_smtp
from fechou.storage.runs import RunStatus, RunStore, StorageError, make_run_key
from fechou.transform.validate import validate_rows

log = get_logger("run")

EXIT_OK = 0
EXIT_DATA_OR_CONFIG = 1
EXIT_DELIVERY = 2


@dataclass(frozen=True, slots=True)
class RunOptions:
    start: dt.date | None = None
    end: dt.date | None = None
    force: bool = False
    dry_run: bool = False
    output_dir: Path = Path("out")


@dataclass(frozen=True, slots=True)
class RunOutcome:
    status: RunStatus | None  # None when the run stopped before having a period
    exit_code: int
    message: str
    period: Period | None = None
    pdf_path: Path | None = None
    summary: str | None = None
    attempts: dict[str, int] = field(default_factory=dict)


def build_deliveries(config: AppConfig, settings: Settings) -> list[Delivery]:
    """Enabled channels, validated against the environment (fail fast)."""
    if config.delivery.telegram.enabled:
        raise ConfigError(
            "Entrega por Telegram ainda não está disponível nesta versão. "
            "Use 'delivery.telegram.enabled: false'."
        )
    deliveries: list[Delivery] = []
    if config.delivery.email.enabled:
        deliveries.append(SmtpDelivery(require_smtp(settings), tuple(config.delivery.email.to)))
    if not deliveries:
        raise ConfigError(
            "Nenhum canal de entrega habilitado em 'delivery'. Habilite o e-mail ou use --dry-run."
        )
    return deliveries


def build_subject(config: AppConfig, period: Period) -> str:
    return config.delivery.email.subject.format(
        start=fmt.date(period.start),
        end=fmt.date(period.end),
        business=config.report.business_name,
    )


def execute_run(
    config: AppConfig,
    options: RunOptions,
    *,
    deliveries: Sequence[Delivery],
    store: RunStore,
    clock: Clock,
    run_id: str,
    sleep: Callable[[float], None] = time.sleep,
) -> RunOutcome:
    source_id = config.source.id
    try:
        period = resolve_period(clock, config.report.zone, options.start, options.end)
    except ValueError as error:
        return RunOutcome(None, EXIT_DATA_OR_CONFIG, f"Período inválido: {error}.")

    log.info(
        "run_started",
        extra={
            "source_id": source_id,
            "period": period.key,
            "force": options.force,
            "dry_run": options.dry_run,
        },
    )

    def finish(
        outcome: RunOutcome,
        *,
        rows_total: int | None = None,
        rows_invalid: int | None = None,
        recipients: Sequence[str] = (),
        error_message: str | None = None,
    ) -> RunOutcome:
        assert outcome.status is not None
        store.record(
            run_id=run_id,
            source_id=source_id,
            period=period,
            status=outcome.status,
            forced=options.force,
            rows_total=rows_total,
            rows_invalid=rows_invalid,
            recipients=recipients,
            error_message=error_message,
            now=clock.now(),
        )
        log.info(
            "run_finished",
            extra={"status": outcome.status.value, "exit_code": outcome.exit_code},
        )
        return outcome

    label = fmt.period(period.start, period.end)

    # 1. Idempotency (RF-11). Dry runs never send, so they skip the check.
    if not options.dry_run and not options.force:
        previous = store.last_success(make_run_key(source_id, period))
        if previous is not None:
            sent_at = fmt.datetime(previous.created_at.astimezone(config.report.zone))
            return finish(
                RunOutcome(
                    RunStatus.SKIPPED,
                    EXIT_OK,
                    f"Nada a fazer: o relatório de {label} já foi enviado em {sent_at}. "
                    "Use --force para reenviar.",
                    period,
                ),
                error_message="already sent",
            )

    # 2. Extract, validate, compute, render. Data errors stop before sending.
    rows_total: int | None = None
    rows_invalid: int | None = None
    try:
        validation = validate_rows(build_source(config).read(), config.columns)
        rows_total, rows_invalid = validation.total, len(validation.invalid)
        log.info("source_read", extra={"rows_total": rows_total, "rows_invalid": rows_invalid})

        report = build_report_data(validation, period, config.report, clock.now())
        if report.metrics.current.is_empty and config.report.empty_period_policy == "skip":
            return finish(
                RunOutcome(
                    RunStatus.SKIPPED,
                    EXIT_OK,
                    f"Sem movimento em {label}; nada enviado (empty_period_policy: skip).",
                    period,
                ),
                rows_total=rows_total,
                rows_invalid=rows_invalid,
                error_message="empty period",
            )

        pdf = render_pdf(report)
        pdf_path = options.output_dir / f"{report_filename(source_id, period)}.pdf"
        try:
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(pdf)
        except OSError as exc:
            raise FechouError(
                f"Não foi possível salvar o PDF em {pdf_path}: {exc.strerror}"
            ) from None
        log.info("report_rendered", extra={"pdf_bytes": len(pdf)})
    except FechouError as error:
        return finish(
            RunOutcome(RunStatus.ERROR, EXIT_DATA_OR_CONFIG, str(error), period),
            rows_total=rows_total,
            rows_invalid=rows_invalid,
            error_message=str(error),
        )

    summary = render_summary_text(report)

    if options.dry_run:
        return finish(
            RunOutcome(
                RunStatus.DRY_RUN,
                EXIT_OK,
                f"Simulação (--dry-run): nada foi enviado. PDF salvo em {pdf_path}.",
                period,
                pdf_path,
                summary,
            ),
            rows_total=rows_total,
            rows_invalid=rows_invalid,
        )

    # 3. Deliver every enabled channel, with retries (RF-14).
    message = ReportMessage(
        subject=build_subject(config, period),
        body=summary,
        attachment=pdf,
        attachment_name=pdf_path.name,
    )
    attempts: dict[str, int] = {}
    failures: list[str] = []
    recipients = [address for delivery in deliveries for address in delivery.recipients]
    for delivery in deliveries:
        try:
            attempts[delivery.channel] = send_with_retries(delivery, message, sleep=sleep)
        except DeliveryError as error:
            failures.append(f"{delivery.channel}: {error}")

    if failures:
        detail = "; ".join(failures)
        return finish(
            RunOutcome(
                RunStatus.DELIVERY_FAILED,
                EXIT_DELIVERY,
                f"Falha na entrega ({detail}). PDF salvo em {pdf_path}.",
                period,
                pdf_path,
                summary,
                attempts,
            ),
            rows_total=rows_total,
            rows_invalid=rows_invalid,
            recipients=recipients,
            error_message=detail,
        )

    success = RunOutcome(
        RunStatus.SUCCESS,
        EXIT_OK,
        f"Relatório de {label} enviado para {len(recipients)} destinatário(s). "
        f"PDF salvo em {pdf_path}.",
        period,
        pdf_path,
        summary,
        attempts,
    )
    try:
        return finish(
            success, rows_total=rows_total, rows_invalid=rows_invalid, recipients=recipients
        )
    except StorageError as error:
        # The e-mail is out; make the risk of a duplicate send explicit.
        log.error("run_not_recorded", extra={"reason": str(error)})
        return RunOutcome(
            RunStatus.SUCCESS,
            EXIT_DATA_OR_CONFIG,
            f"Relatório enviado, mas a execução não foi registrada ({error}). "
            "A próxima execução agendada pode reenviá-lo.",
            period,
            pdf_path,
            summary,
            attempts,
        )
