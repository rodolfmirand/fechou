"""Test doubles for delivery (no network)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from email.message import EmailMessage
from types import TracebackType
from typing import Self

from fechou.deliver.base import DeliveryError, ReportMessage
from fechou.settings import SmtpSettings


@dataclass
class FakeDelivery:
    """Records messages; fails with the queued errors first (one per attempt)."""

    errors: list[DeliveryError] = field(default_factory=list)
    to: tuple[str, ...] = ("dono@exemplo.com",)
    channel: str = "email"
    sent: list[ReportMessage] = field(default_factory=list)
    attempts: int = 0

    @property
    def recipients(self) -> Sequence[str]:
        return self.to

    def send(self, message: ReportMessage) -> None:
        self.attempts += 1
        if self.errors:
            raise self.errors.pop(0)
        self.sent.append(message)


@dataclass
class FakeSMTP:
    """Stands in for ``smtplib.SMTP`` (context manager, login, send_message)."""

    settings: SmtpSettings
    fail_with: BaseException | None = None
    logins: list[tuple[str, str]] = field(default_factory=list)
    messages: list[EmailMessage] = field(default_factory=list)
    closed: bool = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.closed = True

    def login(self, user: str, password: str) -> None:
        self.logins.append((user, password))

    def send_message(self, message: EmailMessage) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.messages.append(message)
