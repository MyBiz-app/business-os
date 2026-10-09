from datetime import date, time

from app.schedule.scheduling import local_to_utc, weekly_occurrences


def test_local_time_is_converted_with_the_business_time_zone() -> None:
    assert local_to_utc(date(2026, 7, 1), time(18, 0), "Asia/Jerusalem").hour == 15  # IDT, UTC+3
    assert local_to_utc(date(2026, 12, 1), time(18, 0), "Asia/Jerusalem").hour == 16  # IST, UTC+2
    assert local_to_utc(date(2026, 12, 1), time(18, 0), "America/New_York").hour == 23


def test_weekly_series_keeps_local_time_across_daylight_saving() -> None:
    # Israel leaves daylight saving time in late October 2026.
    starts = list(
        weekly_occurrences(
            date(2026, 10, 12), date(2026, 11, 9), {0}, time(18, 0), "Asia/Jerusalem"
        )
    )

    assert [s.date().isoformat() for s in starts] == [
        "2026-10-12",
        "2026-10-19",
        "2026-10-26",
        "2026-11-02",
        "2026-11-09",
    ]
    assert {s.hour for s in starts[:2]} == {15}
    assert {s.hour for s in starts[2:]} == {16}


def test_multiple_weekdays_and_bounds() -> None:
    # Sunday (6) and Wednesday (2), from a Thursday to the next Thursday.
    starts = list(
        weekly_occurrences(date(2026, 10, 1), date(2026, 10, 8), {6, 2}, time(7, 0), "UTC")
    )

    assert [s.date().isoformat() for s in starts] == ["2026-10-04", "2026-10-07"]
