import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from fechou.clock import FixedClock, SystemClock
from fechou.domain.period import Period, previous_full_week, resolve_period

SP = ZoneInfo("America/Sao_Paulo")
UTC = dt.UTC


def _local(year: int, month: int, day: int, hour: int, minute: int) -> dt.datetime:
    return dt.datetime(year, month, day, hour, minute, tzinfo=SP)


def _week(start: str, end: str) -> Period:
    return Period(dt.date.fromisoformat(start), dt.date.fromisoformat(end))


class TestPeriod:
    def test_days_iteration_and_membership(self) -> None:
        period = _week("2026-11-09", "2026-11-15")

        assert period.days == 7
        days = list(period)
        assert (days[0], days[-1]) == (dt.date(2026, 11, 9), dt.date(2026, 11, 15))
        assert dt.date(2026, 11, 15) in period
        assert dt.date(2026, 11, 16) not in period
        assert "2026-11-10" not in period

    def test_single_day_period(self) -> None:
        assert Period(dt.date(2026, 1, 1), dt.date(2026, 1, 1)).days == 1

    def test_end_before_start_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="anterior à inicial"):
            _week("2026-11-15", "2026-11-09")

    def test_previous_has_same_length_and_is_adjacent(self) -> None:
        assert _week("2026-11-09", "2026-11-15").previous() == _week("2026-11-02", "2026-11-08")
        # Custom 10-day period -> previous 10 days.
        assert _week("2026-11-11", "2026-11-20").previous() == _week("2026-11-01", "2026-11-10")

    def test_previous_crosses_year_and_leap_day(self) -> None:
        assert _week("2027-01-04", "2027-01-10").previous() == _week("2026-12-28", "2027-01-03")
        assert _week("2028-03-01", "2028-03-07").previous() == _week("2028-02-23", "2028-02-29")

    def test_key(self) -> None:
        assert _week("2026-11-09", "2026-11-15").key == "2026-11-09:2026-11-15"


class TestPreviousFullWeek:
    @pytest.mark.parametrize(
        ("now", "expected"),
        [
            # Monday morning: last week is the one that just ended.
            (_local(2026, 11, 16, 7, 0), ("2026-11-09", "2026-11-15")),
            # Monday right after midnight.
            (_local(2026, 11, 16, 0, 0), ("2026-11-09", "2026-11-15")),
            # Sunday night: the current week is not complete yet.
            (_local(2026, 11, 15, 23, 59), ("2026-11-02", "2026-11-08")),
            # Mid-week.
            (_local(2026, 11, 19, 12, 0), ("2026-11-09", "2026-11-15")),
            # Year boundary: week spans two years.
            (_local(2027, 1, 4, 8, 0), ("2026-12-28", "2027-01-03")),
            (_local(2027, 1, 1, 8, 0), ("2026-12-21", "2026-12-27")),
        ],
    )
    def test_local_time(self, now: dt.datetime, expected: tuple[str, str]) -> None:
        assert previous_full_week(now, SP) == _week(*expected)

    def test_utc_instant_is_converted_to_local_timezone(self) -> None:
        # Monday 02:00 UTC is still Sunday 23:00 in Sao Paulo (UTC-3).
        now = dt.datetime(2026, 11, 16, 2, 0, tzinfo=UTC)

        assert previous_full_week(now, SP) == _week("2026-11-02", "2026-11-08")
        assert previous_full_week(now, ZoneInfo("UTC")) == _week("2026-11-09", "2026-11-15")

    def test_naive_datetime_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            previous_full_week(dt.datetime(2026, 11, 16), SP)


class TestResolvePeriod:
    clock = FixedClock(dt.datetime(2026, 11, 20, 12, 0, tzinfo=UTC))

    def test_defaults_to_previous_full_week(self) -> None:
        assert resolve_period(self.clock, SP) == _week("2026-11-09", "2026-11-15")

    def test_explicit_bounds_win(self) -> None:
        period = resolve_period(self.clock, SP, dt.date(2026, 10, 1), dt.date(2026, 10, 31))
        assert period == _week("2026-10-01", "2026-10-31")

    @pytest.mark.parametrize(
        ("start", "end"), [(dt.date(2026, 10, 1), None), (None, dt.date(2026, 10, 31))]
    )
    def test_bounds_must_come_together(self, start: dt.date | None, end: dt.date | None) -> None:
        with pytest.raises(ValueError, match="juntos"):
            resolve_period(self.clock, SP, start, end)


class TestClocks:
    @freeze_time("2026-11-16 02:00:00")  # naive => UTC for freezegun
    def test_system_clock_is_aware_utc_and_drives_the_period(self) -> None:
        now = SystemClock().now()

        assert now == dt.datetime(2026, 11, 16, 2, 0, tzinfo=UTC)
        assert resolve_period(SystemClock(), SP) == _week("2026-11-02", "2026-11-08")

    def test_fixed_clock_requires_aware_datetime(self) -> None:
        with pytest.raises(ValueError):
            FixedClock(dt.datetime(2026, 11, 16))
