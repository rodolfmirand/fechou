"""CLI-level tests for ``run`` and ``init-config`` (env, exit codes, output)."""

import datetime as dt
import json
import smtplib
from email.message import EmailMessage
from pathlib import Path
from types import TracebackType
from typing import ClassVar, Self

import pytest
from typer.testing import CliRunner

from fechou import cli
from fechou.clock import FixedClock
from fechou.config import load_config
from tests.conftest import EXAMPLES_DIR, requires_pdf

CONFIG = str(EXAMPLES_DIR / "config.example.yaml")
CLOCK = FixedClock(dt.datetime(2026, 11, 18, 12, 0, tzinfo=dt.UTC))
runner = CliRunner()


class RecordingSMTP:
    """Replaces ``smtplib.SMTP``; keeps every message sent in the test."""

    sent: ClassVar[list[EmailMessage]] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.address = (host, port)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def send_message(self, message: EmailMessage) -> None:
        RecordingSMTP.sent.append(message)


@pytest.fixture
def smtp_env(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("SMTP_SECURITY", "none")
    monkeypatch.setenv("SMTP_FROM", "Fechou <relatorios@exemplo.com>")
    monkeypatch.setattr(smtplib, "SMTP", RecordingSMTP)
    monkeypatch.setattr(cli, "SystemClock", lambda: CLOCK)
    RecordingSMTP.sent = []
    return clean_env


@requires_pdf
def test_run_sends_once_then_skips(smtp_env: Path) -> None:
    first = runner.invoke(cli.app, ["run", "-c", CONFIG])
    second = runner.invoke(cli.app, ["run", "-c", CONFIG])

    assert first.exit_code == cli.EXIT_OK, first.output
    assert "enviado para 1 destinatário(s)" in first.stdout
    assert second.exit_code == cli.EXIT_OK
    assert "Nada a fazer" in second.stdout
    assert len(RecordingSMTP.sent) == 1
    assert RecordingSMTP.sent[0]["Subject"] == "Fechamento da semana 09/11/2026 a 15/11/2026"
    # Default locations relative to the working directory.
    assert (smtp_env / "data" / "fechou.db").exists()
    assert len(list((smtp_env / "out").glob("*.pdf"))) == 1


@requires_pdf
def test_run_logs_are_json_with_run_id_and_no_personal_data(smtp_env: Path) -> None:
    result = runner.invoke(cli.app, ["run", "-c", CONFIG])

    events = [json.loads(line) for line in result.stderr.splitlines() if line.startswith("{")]
    assert [e["event"] for e in events] == [
        "run_started",
        "source_read",
        "report_rendered",
        "delivered",
        "run_finished",
    ]
    assert len({e["run_id"] for e in events}) == 1
    assert events[1]["rows_total"] == 785
    assert "dono@exemplo.com" not in result.stderr
    assert "Camiseta" not in result.stderr


@requires_pdf
def test_run_dry_run_needs_no_smtp(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "SystemClock", lambda: CLOCK)

    result = runner.invoke(cli.app, ["run", "-c", CONFIG, "--dry-run", "-o", "relatorios"])

    assert result.exit_code == cli.EXIT_OK, result.output
    assert "Simulação (--dry-run): nada foi enviado." in result.stdout
    assert "Faturamento: R$ 16.770,70" in result.stdout
    assert (clean_env / "relatorios" / "fechou_loja-demo_2026-11-09_2026-11-15.pdf").exists()


def test_run_without_smtp_env_fails_fast(clean_env: Path) -> None:
    result = runner.invoke(cli.app, ["run", "-c", CONFIG])

    assert result.exit_code == cli.EXIT_DATA_OR_CONFIG
    assert "faltam variáveis de ambiente: SMTP_HOST, SMTP_FROM" in result.stderr
    assert not (clean_env / "data").exists()  # nothing ran


def test_run_rejects_bad_date(clean_env: Path) -> None:
    result = runner.invoke(cli.app, ["run", "-c", CONFIG, "--start", "15/11/2026"])

    assert result.exit_code != cli.EXIT_OK


def test_run_requires_both_bounds(smtp_env: Path) -> None:
    result = runner.invoke(cli.app, ["run", "-c", CONFIG, "--start", "2026-11-09"])

    assert result.exit_code == cli.EXIT_DATA_OR_CONFIG
    assert "informe --start e --end juntos" in result.stderr


def test_delivery_failure_exit_code(smtp_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise smtplib.SMTPAuthenticationError(535, b"no")

    monkeypatch.setattr(RecordingSMTP, "send_message", refuse)

    result = runner.invoke(cli.app, ["run", "-c", CONFIG])

    if "WeasyPrint" in result.output:  # pragma: no cover - machine without Pango
        pytest.skip("PDF rendering unavailable")
    assert result.exit_code == cli.EXIT_DELIVERY
    assert "Falha na entrega" in result.stderr


class TestInitConfig:
    def test_creates_a_valid_config(self, clean_env: Path) -> None:
        result = runner.invoke(cli.app, ["init-config"])

        assert result.exit_code == cli.EXIT_OK
        created = clean_env / "config.yaml"
        config = load_config(created)
        assert config.source.id == "minha-loja"
        assert config.report.business_name == "Minha Loja"

    def test_refuses_to_overwrite(self, clean_env: Path) -> None:
        (clean_env / "config.yaml").write_text("meu: arquivo\n", encoding="utf-8")

        result = runner.invoke(cli.app, ["init-config"])

        assert result.exit_code == cli.EXIT_DATA_OR_CONFIG
        assert "já existe" in result.stderr
        assert (clean_env / "config.yaml").read_text(encoding="utf-8") == "meu: arquivo\n"

    def test_overwrite_flag_and_custom_path(self, clean_env: Path) -> None:
        target = clean_env / "conf" / "loja.yaml"

        result = runner.invoke(cli.app, ["init-config", "-o", str(target), "--overwrite"])

        assert result.exit_code == cli.EXIT_OK
        assert target.exists()
