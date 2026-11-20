"""Injectable clock, so period logic never reads the real time directly."""

import datetime as dt
from dataclasses import dataclass
from typing import Protocol


class Clock(Protocol):
    def now(self) -> dt.datetime:
        """Current time as a timezone-aware datetime."""
        ...


class SystemClock:
    def now(self) -> dt.datetime:
        return dt.datetime.now(dt.UTC)


@dataclass(frozen=True, slots=True)
class FixedClock:
    """A clock stuck at a given aware instant (tests and reproducible runs)."""

    instant: dt.datetime

    def __post_init__(self) -> None:
        if self.instant.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")

    def now(self) -> dt.datetime:
        return self.instant
