"""Report periods (inclusive date ranges) and the default "previous week" rule."""

import datetime as dt
from collections.abc import Iterator
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from fechou.clock import Clock


@dataclass(frozen=True, slots=True)
class Period:
    """Inclusive range of calendar days: ``start <= day <= end``."""

    start: dt.date
    end: dt.date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(
                f"data final ({self.end:%d/%m/%Y}) anterior à inicial ({self.start:%d/%m/%Y})"
            )

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def __contains__(self, day: object) -> bool:
        return isinstance(day, dt.date) and self.start <= day <= self.end

    def __iter__(self) -> Iterator[dt.date]:
        for offset in range(self.days):
            yield self.start + dt.timedelta(days=offset)

    def previous(self) -> "Period":
        """The period of the same length that ends the day before this one starts."""
        end = self.start - dt.timedelta(days=1)
        return Period(start=end - dt.timedelta(days=self.days - 1), end=end)

    @property
    def key(self) -> str:
        """Stable identifier used in run keys: ``YYYY-MM-DD:YYYY-MM-DD``."""
        return f"{self.start.isoformat()}:{self.end.isoformat()}"


def previous_full_week(now: dt.datetime, timezone: ZoneInfo) -> Period:
    """Last complete Monday-to-Sunday week before the week that contains ``now``.

    ``now`` must be aware; it is converted to ``timezone`` first, so a run at
    02:00 UTC on a Monday still counts as Sunday in America/Sao_Paulo.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    today = now.astimezone(timezone).date()
    this_monday = today - dt.timedelta(days=today.weekday())
    start = this_monday - dt.timedelta(days=7)
    return Period(start=start, end=start + dt.timedelta(days=6))


def resolve_period(
    clock: Clock,
    timezone: ZoneInfo,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> Period:
    """Explicit ``--start``/``--end`` win; otherwise use the previous full week.

    Both bounds must be given together.
    """
    if start is None and end is None:
        return previous_full_week(clock.now(), timezone)
    if start is None or end is None:
        raise ValueError("informe --start e --end juntos")
    return Period(start=start, end=end)
