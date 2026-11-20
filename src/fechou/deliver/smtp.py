"""E-mail delivery over plain SMTP (any provider: Gmail app password, Mailpit, ...)."""

import smtplib
import ssl
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from fechou.deliver.base import (
    PermanentDeliveryError,
    ReportMessage,
    TransientDeliveryError,
)
from fechou.settings import SmtpSettings

EMAIL_FOOTER = "\n\n—\nRelatório gerado automaticamente pelo Fechou. O PDF completo está em anexo."

SmtpFactory = Callable[[SmtpSettings], smtplib.SMTP]


def connect(settings: SmtpSettings) -> smtplib.SMTP:
    """Open an SMTP connection according to ``SMTP_SECURITY``."""
    context = ssl.create_default_context()
    client: smtplib.SMTP
    if settings.security == "ssl":
        client = smtplib.SMTP_SSL(
            settings.host, settings.port, timeout=settings.timeout, context=context
        )
    else:
        client = smtplib.SMTP(settings.host, settings.port, timeout=settings.timeout)
        if settings.security == "starttls":
            client.starttls(context=context)
    return client


def build_email(settings: SmtpSettings, to: Sequence[str], message: ReportMessage) -> EmailMessage:
    email = EmailMessage()
    email["From"] = settings.sender
    email["To"] = ", ".join(to)
    email["Subject"] = message.subject
    email["Date"] = formatdate(localtime=False, usegmt=True)
    email["Message-ID"] = make_msgid(domain="fechou.local")
    email.set_content(message.body + EMAIL_FOOTER)
    email.add_attachment(
        message.attachment,
        maintype="application",
        subtype="pdf",
        filename=message.attachment_name,
    )
    return email


@dataclass(frozen=True, slots=True)
class SmtpDelivery:
    settings: SmtpSettings
    to: tuple[str, ...]
    factory: SmtpFactory = field(default=connect)
    channel: str = "email"

    @property
    def recipients(self) -> Sequence[str]:
        return self.to

    def send(self, message: ReportMessage) -> None:
        email = build_email(self.settings, self.to, message)
        try:
            with self.factory(self.settings) as client:
                if self.settings.user and self.settings.password is not None:
                    client.login(self.settings.user, self.settings.password.get_secret_value())
                client.send_message(email)
        except smtplib.SMTPAuthenticationError:
            raise PermanentDeliveryError(
                "o servidor SMTP recusou o usuário/senha (confira SMTP_USER e SMTP_PASSWORD)"
            ) from None
        except smtplib.SMTPRecipientsRefused:
            raise PermanentDeliveryError("o servidor SMTP recusou os destinatários") from None
        except smtplib.SMTPSenderRefused:
            raise PermanentDeliveryError(
                "o servidor SMTP recusou o remetente (confira SMTP_FROM)"
            ) from None
        except smtplib.SMTPResponseException as exc:
            # 4xx = temporary, 5xx = permanent (RFC 5321).
            error_class = (
                TransientDeliveryError if 400 <= exc.smtp_code < 500 else PermanentDeliveryError
            )
            raise error_class(f"o servidor SMTP respondeu {exc.smtp_code}") from None
        except smtplib.SMTPNotSupportedError:
            raise PermanentDeliveryError(
                "o servidor não suporta o modo pedido (ajuste SMTP_SECURITY)"
            ) from None
        except ssl.SSLError as exc:
            reason = getattr(exc, "reason", None) or type(exc).__name__
            raise PermanentDeliveryError(
                f"falha de TLS ({reason}); confira SMTP_SECURITY e SMTP_PORT"
            ) from None
        except (TimeoutError, smtplib.SMTPException, OSError) as exc:
            raise TransientDeliveryError(
                f"falha de conexão com {self.settings.host}:{self.settings.port} "
                f"({type(exc).__name__})"
            ) from None
