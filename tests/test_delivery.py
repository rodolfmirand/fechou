import smtplib
import ssl
from typing import cast

import pytest
from pydantic import SecretStr

from fechou.deliver.base import (
    PermanentDeliveryError,
    ReportMessage,
    TransientDeliveryError,
    send_with_retries,
)
from fechou.deliver.smtp import EMAIL_FOOTER, SmtpDelivery, build_email
from fechou.settings import SmtpSettings
from tests.fakes import FakeDelivery, FakeSMTP

MESSAGE = ReportMessage(
    subject="Fechamento da semana 09/11/2026 a 15/11/2026",
    body="Resumo — R$ 1.234,56",
    attachment=b"%PDF-1.7 fake",
    attachment_name="fechou_loja_2026-11-09_2026-11-15.pdf",
)
SETTINGS = SmtpSettings(
    host="smtp.exemplo.com",
    port=587,
    sender="Fechou <relatorios@exemplo.com>",
    security="starttls",
    timeout=5,
    user="usuario",
    password=SecretStr("segredo"),
)


class TestRetries:
    def test_first_attempt_succeeds(self) -> None:
        delivery = FakeDelivery()
        waits: list[float] = []

        assert send_with_retries(delivery, MESSAGE, sleep=waits.append) == 1
        assert delivery.sent == [MESSAGE]
        assert waits == []

    def test_transient_errors_are_retried_with_growing_waits(self) -> None:
        delivery = FakeDelivery(errors=[TransientDeliveryError("rede")] * 2)
        waits: list[float] = []

        assert send_with_retries(delivery, MESSAGE, sleep=waits.append) == 3
        assert waits == [2.0, 4.0]
        assert len(delivery.sent) == 1

    def test_gives_up_after_three_retries(self) -> None:
        delivery = FakeDelivery(errors=[TransientDeliveryError("rede")] * 10)
        waits: list[float] = []

        with pytest.raises(TransientDeliveryError):
            send_with_retries(delivery, MESSAGE, sleep=waits.append)

        assert delivery.attempts == 4  # 1 attempt + 3 retries
        assert waits == [2.0, 4.0, 8.0]
        assert delivery.sent == []

    def test_permanent_errors_are_not_retried(self) -> None:
        delivery = FakeDelivery(errors=[PermanentDeliveryError("senha errada")])
        waits: list[float] = []

        with pytest.raises(PermanentDeliveryError):
            send_with_retries(delivery, MESSAGE, sleep=waits.append)

        assert delivery.attempts == 1
        assert waits == []


class TestEmailMessage:
    def test_headers_body_and_attachment(self) -> None:
        email = build_email(SETTINGS, ["dono@exemplo.com", "socio@exemplo.com"], MESSAGE)

        assert email["From"] == "Fechou <relatorios@exemplo.com>"
        assert email["To"] == "dono@exemplo.com, socio@exemplo.com"
        assert email["Subject"] == MESSAGE.subject
        assert email["Message-ID"]
        body = email.get_body(preferencelist=("plain",))
        assert body is not None
        assert body.get_content() == MESSAGE.body + EMAIL_FOOTER + "\n"
        attachments = list(email.iter_attachments())
        assert len(attachments) == 1
        assert attachments[0].get_content_type() == "application/pdf"
        assert attachments[0].get_filename() == MESSAGE.attachment_name
        assert attachments[0].get_payload(decode=True) == MESSAGE.attachment


class TestSmtpDelivery:
    def _delivery(self, fake: FakeSMTP, settings: SmtpSettings = SETTINGS) -> SmtpDelivery:
        return SmtpDelivery(
            settings, ("dono@exemplo.com",), factory=lambda _: cast(smtplib.SMTP, fake)
        )

    def test_logs_in_and_sends(self) -> None:
        fake = FakeSMTP(SETTINGS)

        self._delivery(fake).send(MESSAGE)

        assert fake.logins == [("usuario", "segredo")]
        assert len(fake.messages) == 1
        assert fake.closed

    def test_no_login_without_credentials(self) -> None:
        settings = SmtpSettings("localhost", 1025, "r@exemplo.com", "none", 5)
        fake = FakeSMTP(settings)

        self._delivery(fake, settings).send(MESSAGE)

        assert fake.logins == []
        assert len(fake.messages) == 1

    @pytest.mark.parametrize(
        ("error", "expected", "fragment"),
        [
            (smtplib.SMTPAuthenticationError(535, b"bad"), PermanentDeliveryError, "SMTP_USER"),
            (smtplib.SMTPRecipientsRefused({}), PermanentDeliveryError, "destinatários"),
            (smtplib.SMTPSenderRefused(550, b"no", "x"), PermanentDeliveryError, "SMTP_FROM"),
            (smtplib.SMTPDataError(451, b"try later"), TransientDeliveryError, "451"),
            (smtplib.SMTPDataError(554, b"rejected"), PermanentDeliveryError, "554"),
            (smtplib.SMTPServerDisconnected("bye"), TransientDeliveryError, "conexão"),
            (TimeoutError(), TransientDeliveryError, "conexão"),
            (ConnectionRefusedError(), TransientDeliveryError, "smtp.exemplo.com:587"),
            (ssl.SSLError(1, "WRONG_VERSION_NUMBER"), PermanentDeliveryError, "SMTP_SECURITY"),
        ],
    )
    def test_errors_are_classified(
        self, error: BaseException, expected: type[Exception], fragment: str
    ) -> None:
        fake = FakeSMTP(SETTINGS, fail_with=error)

        with pytest.raises(expected) as info:
            self._delivery(fake).send(MESSAGE)

        assert fragment in str(info.value)
        assert "segredo" not in str(info.value)
