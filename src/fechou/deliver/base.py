"""Delivery port, shared message type and retry policy."""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from fechou.errors import FechouError
from fechou.logging_setup import get_logger

log = get_logger("deliver")

# RF-14 / section 8.2: retry up to 3 times with growing waits (2 s, 4 s, 8 s).
DEFAULT_RETRIES = 3
DEFAULT_BASE_DELAY = 2.0


class DeliveryError(FechouError):
    """A report could not be delivered."""


class TransientDeliveryError(DeliveryError):
    """Worth retrying (network failure, timeout, temporary 4xx from the server)."""


class PermanentDeliveryError(DeliveryError):
    """Retrying will not help (bad credentials, rejected recipients, 5xx)."""


@dataclass(frozen=True, slots=True)
class ReportMessage:
    subject: str
    body: str
    attachment: bytes
    attachment_name: str


class Delivery(Protocol):
    @property
    def channel(self) -> str:
        """Short channel name for logs and the runs table (e.g. ``email``)."""
        ...

    @property
    def recipients(self) -> Sequence[str]: ...

    def send(self, message: ReportMessage) -> None:
        """Send once. Raises a ``DeliveryError`` subclass on failure."""
        ...


def send_with_retries(
    delivery: Delivery,
    message: ReportMessage,
    *,
    retries: int = DEFAULT_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Send, retrying transient failures with exponential backoff.

    Returns the number of attempts used. Re-raises the last error when the
    retries are exhausted or the error is permanent.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            delivery.send(message)
        except PermanentDeliveryError as error:
            log.error(
                "delivery_failed",
                extra={"channel": delivery.channel, "attempt": attempt, "reason": str(error)},
            )
            raise
        except TransientDeliveryError as error:
            if attempt > retries:
                log.error(
                    "delivery_failed",
                    extra={"channel": delivery.channel, "attempt": attempt, "reason": str(error)},
                )
                raise
            delay = base_delay * 2 ** (attempt - 1)
            log.warning(
                "delivery_retry",
                extra={
                    "channel": delivery.channel,
                    "attempt": attempt,
                    "wait_seconds": delay,
                    "reason": str(error),
                },
            )
            sleep(delay)
        else:
            log.info("delivered", extra={"channel": delivery.channel, "attempt": attempt})
            return attempt
