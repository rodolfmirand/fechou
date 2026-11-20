"""Integration tests for ``fechou run`` (example CSV, fake delivery, real PDF)."""

import datetime as dt
from pathlib import Path

import pytest

from fechou.clock import FixedClock
from fechou.config import AppConfig, load_config
from fechou.deliver.base import PermanentDeliveryError, TransientDeliveryError
from fechou.domain.period import Period
from fechou.errors import ConfigError
from fechou.runner import (
    EXIT_DATA_OR_CONFIG,
    EXIT_DELIVERY,
    EXIT_OK,
    RunOptions,
    RunOutcome,
    build_deliveries,
    build_subject,
    execute_run,
)
from fechou.settings import Settings
from fechou.storage.runs import RunStatus, RunStore
from tests.conftest import EXAMPLES_DIR, requires_pdf
from tests.fakes import FakeDelivery

# Wednesday 2026-11-18 -> default period is 09-15/11/2026.
CLOCK = FixedClock(dt.datetime(2026, 11, 18, 12, 0, tzinfo=dt.UTC))
WEEK_KEY = "loja-demo:2026-11-09:2026-11-15"
CLOCK_PERIOD = Period(dt.date(2026, 11, 9), dt.date(2026, 11, 15))


@pytest.fixture
def config() -> AppConfig:
    return load_config(EXAMPLES_DIR / "config.example.yaml")


@pytest.fixture
def store(tmp_path: Path) -> RunStore:
    return RunStore(tmp_path / "fechou.db")


def _run(
    config: AppConfig,
    store: RunStore,
    tmp_path: Path,
    delivery: FakeDelivery,
    *,
    start: dt.date | None = None,
    end: dt.date | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[RunOutcome, list[float]]:
    waits: list[float] = []
    options = RunOptions(
        start=start, end=end, force=force, dry_run=dry_run, output_dir=tmp_path / "out"
    )
    outcome = execute_run(
        config,
        options,
        deliveries=[delivery],
        store=store,
        clock=CLOCK,
        run_id="test-run",
        sleep=waits.append,
    )
    return outcome, waits


@requires_pdf
class TestRun:
    def test_sends_previous_week_and_records_success(
        self, config: AppConfig, store: RunStore, tmp_path: Path
    ) -> None:
        delivery = FakeDelivery()

        outcome = execute_run(
            config,
            RunOptions(output_dir=tmp_path / "out"),
            deliveries=[delivery],
            store=store,
            clock=CLOCK,
            run_id="r1",
        )

        assert outcome.exit_code == EXIT_OK
        assert outcome.status == RunStatus.SUCCESS
        assert "enviado para 1 destinatário(s)" in outcome.message
        assert outcome.pdf_path is not None and outcome.pdf_path.exists()
        assert len(delivery.sent) == 1
        message = delivery.sent[0]
        assert message.subject == "Fechamento da semana 09/11/2026 a 15/11/2026"
        assert "Faturamento: R$ 16.770,70" in message.body
        assert message.attachment.startswith(b"%PDF-")
        assert message.attachment_name == "fechou_loja-demo_2026-11-09_2026-11-15.pdf"
        record = store.last_success(WEEK_KEY)
        assert record is not None
        assert (record.rows_total, record.rows_invalid) == (785, 6)
        assert record.recipients == ("dono@exemplo.com",)

    def test_running_twice_does_not_send_twice(
        self, config: AppConfig, store: RunStore, tmp_path: Path
    ) -> None:
        delivery = FakeDelivery()
        _run(config, store, tmp_path, delivery)

        outcome = execute_run(
            config,
            RunOptions(output_dir=tmp_path / "out"),
            deliveries=[delivery],
            store=store,
            clock=CLOCK,
            run_id="r2",
        )

        assert outcome.exit_code == EXIT_OK
        assert outcome.status == RunStatus.SKIPPED
        assert "já foi enviado em 18/11/2026 09:00" in outcome.message
        assert len(delivery.sent) == 1
        assert [r.status for r in store.history()] == [RunStatus.SKIPPED, RunStatus.SUCCESS]

    def test_force_resends(self, config: AppConfig, store: RunStore, tmp_path: Path) -> None:
        delivery = FakeDelivery()
        _run(config, store, tmp_path, delivery)

        outcome, _ = _run(config, store, tmp_path, delivery, force=True)

        assert outcome.status == RunStatus.SUCCESS
        assert len(delivery.sent) == 2
        assert store.history()[0].forced is True

    def test_dry_run_saves_pdf_and_sends_nothing(
        self, config: AppConfig, store: RunStore, tmp_path: Path
    ) -> None:
        delivery = FakeDelivery()

        outcome = execute_run(
            config,
            RunOptions(dry_run=True, output_dir=tmp_path / "out"),
            deliveries=[],
            store=store,
            clock=CLOCK,
            run_id="dry",
        )

        assert outcome.exit_code == EXIT_OK
        assert outcome.status == RunStatus.DRY_RUN
        assert outcome.pdf_path == tmp_path / "out" / "fechou_loja-demo_2026-11-09_2026-11-15.pdf"
        assert outcome.pdf_path.exists()
        assert outcome.summary is not None and "R$ 16.770,70" in outcome.summary
        assert delivery.sent == []
        # A dry run never blocks the real one.
        assert store.last_success(WEEK_KEY) is None

    def test_dry_run_ignores_previous_success(
        self, config: AppConfig, store: RunStore, tmp_path: Path
    ) -> None:
        _run(config, store, tmp_path, FakeDelivery())

        outcome, _ = _run(config, store, tmp_path, FakeDelivery(), dry_run=True)

        assert outcome.status == RunStatus.DRY_RUN

    def test_explicit_period(self, config: AppConfig, store: RunStore, tmp_path: Path) -> None:
        delivery = FakeDelivery()

        outcome, _ = _run(
            config,
            store,
            tmp_path,
            delivery,
            start=dt.date(2026, 10, 1),
            end=dt.date(2026, 10, 31),
        )

        assert outcome.status == RunStatus.SUCCESS
        assert delivery.sent[0].subject == "Fechamento da semana 01/10/2026 a 31/10/2026"
        assert store.last_success("loja-demo:2026-10-01:2026-10-31") is not None

    def test_transient_failure_then_success(
        self, config: AppConfig, store: RunStore, tmp_path: Path
    ) -> None:
        delivery = FakeDelivery(errors=[TransientDeliveryError("rede")])

        outcome, waits = _run(config, store, tmp_path, delivery)

        assert outcome.status == RunStatus.SUCCESS
        assert outcome.attempts == {"email": 2}
        assert waits == [2.0]

    def test_delivery_failure_exits_2_and_allows_retry_later(
        self, config: AppConfig, store: RunStore, tmp_path: Path
    ) -> None:
        delivery = FakeDelivery(errors=[TransientDeliveryError("rede")] * 4)

        outcome, waits = _run(config, store, tmp_path, delivery)

        assert outcome.exit_code == EXIT_DELIVERY
        assert outcome.status == RunStatus.DELIVERY_FAILED
        assert waits == [2.0, 4.0, 8.0]
        assert store.history()[0].error_message == "email: rede"
        # Not marked as sent: the next scheduled run tries again.
        assert store.last_success(WEEK_KEY) is None
        outcome, _ = _run(config, store, tmp_path, delivery)
        assert outcome.status == RunStatus.SUCCESS

    def test_permanent_failure_is_not_retried(
        self, config: AppConfig, store: RunStore, tmp_path: Path
    ) -> None:
        delivery = FakeDelivery(errors=[PermanentDeliveryError("senha recusada")])

        outcome, waits = _run(config, store, tmp_path, delivery)

        assert outcome.exit_code == EXIT_DELIVERY
        assert waits == []
        assert "senha recusada" in outcome.message

    def test_empty_period_send_empty_policy(
        self, config: AppConfig, store: RunStore, tmp_path: Path
    ) -> None:
        delivery = FakeDelivery()

        outcome, _ = _run(
            config, store, tmp_path, delivery, start=dt.date(2030, 1, 1), end=dt.date(2030, 1, 7)
        )

        assert outcome.status == RunStatus.SUCCESS
        assert "Sem movimento no período." in delivery.sent[0].body


class TestRunWithoutPdf:
    """Paths that stop before rendering (no Pango needed)."""

    def test_empty_period_skip_policy(
        self, config: AppConfig, store: RunStore, tmp_path: Path
    ) -> None:
        skip = config.model_copy(
            update={"report": config.report.model_copy(update={"empty_period_policy": "skip"})}
        )
        delivery = FakeDelivery()

        outcome, _ = _run(
            skip, store, tmp_path, delivery, start=dt.date(2030, 1, 1), end=dt.date(2030, 1, 7)
        )

        assert outcome.exit_code == EXIT_OK
        assert outcome.status == RunStatus.SKIPPED
        assert "Sem movimento" in outcome.message
        assert delivery.sent == []

    def test_source_error_is_recorded_and_nothing_is_sent(
        self, config: AppConfig, store: RunStore, tmp_path: Path
    ) -> None:
        missing = config.model_copy(
            update={"source": config.source.model_copy(update={"path": tmp_path / "nada.csv"})}
        )
        delivery = FakeDelivery()

        outcome, _ = _run(missing, store, tmp_path, delivery)

        assert outcome.exit_code == EXIT_DATA_OR_CONFIG
        assert outcome.status == RunStatus.ERROR
        assert "não encontrado" in outcome.message
        assert delivery.sent == []
        assert store.history()[0].status == RunStatus.ERROR

    def test_invalid_period(self, config: AppConfig, store: RunStore, tmp_path: Path) -> None:
        outcome, _ = _run(config, store, tmp_path, FakeDelivery(), start=dt.date(2026, 11, 1))

        assert outcome.exit_code == EXIT_DATA_OR_CONFIG
        assert "juntos" in outcome.message
        assert store.history() == []

    def test_already_sent_check_happens_before_reading(
        self, config: AppConfig, store: RunStore, tmp_path: Path
    ) -> None:
        store.record(
            run_id="old",
            source_id="loja-demo",
            period=CLOCK_PERIOD,
            status=RunStatus.SUCCESS,
        )
        missing = config.model_copy(
            update={"source": config.source.model_copy(update={"path": tmp_path / "nada.csv"})}
        )

        outcome, _ = _run(missing, store, tmp_path, FakeDelivery())

        assert outcome.status == RunStatus.SKIPPED


class TestDeliveriesAndSubject:
    def test_build_deliveries_requires_smtp_env(self, config: AppConfig, clean_env: Path) -> None:
        with pytest.raises(ConfigError, match="SMTP_HOST"):
            build_deliveries(config, Settings())

    def test_build_deliveries_with_env(
        self, config: AppConfig, clean_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SMTP_HOST", "localhost")
        monkeypatch.setenv("SMTP_FROM", "r@exemplo.com")

        deliveries = build_deliveries(config, Settings())

        assert [d.channel for d in deliveries] == ["email"]
        assert list(deliveries[0].recipients) == ["dono@exemplo.com"]

    def test_no_channel_enabled(self, config: AppConfig, clean_env: Path) -> None:
        email_off = config.delivery.email.model_copy(update={"enabled": False})
        no_channels = config.model_copy(
            update={"delivery": config.delivery.model_copy(update={"email": email_off})}
        )

        with pytest.raises(ConfigError, match="Nenhum canal"):
            build_deliveries(no_channels, Settings())

    def test_telegram_not_available_yet(self, config: AppConfig, clean_env: Path) -> None:
        telegram_on = config.delivery.telegram.model_copy(update={"enabled": True})
        with_telegram = config.model_copy(
            update={"delivery": config.delivery.model_copy(update={"telegram": telegram_on})}
        )

        with pytest.raises(ConfigError, match="Telegram"):
            build_deliveries(with_telegram, Settings())

    def test_subject_variables(self, config: AppConfig) -> None:
        email = config.delivery.email.model_copy(update={"subject": "{business}: {start}-{end}"})
        custom = config.model_copy(
            update={"delivery": config.delivery.model_copy(update={"email": email})}
        )

        assert build_subject(custom, CLOCK_PERIOD) == "Loja Demo: 09/11/2026-15/11/2026"
