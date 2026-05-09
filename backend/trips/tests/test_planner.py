from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from trips.planner import RouteSummary, plan_trip


START_TIME = datetime(2026, 5, 9, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def test_short_trip_includes_pickup_drive_and_dropoff_without_rest():
    plan = plan_trip(
        start_datetime=START_TIME,
        pickup_location="Austin, TX",
        dropoff_location="Phoenix, AZ",
        route=RouteSummary(distance_miles=Decimal("500"), average_speed_mph=Decimal("50")),
        current_cycle_used_hours=Decimal("10"),
    )

    assert [event.status for event in plan.events] == ["on_duty", "driving", "on_duty"]
    assert plan.events[0].location == "Austin, TX"
    assert plan.events[-1].location == "Phoenix, AZ"
    assert plan.totals["driving_hours"] == Decimal("10.00")
    assert plan.totals["off_duty_hours"] == Decimal("0.00")


def test_long_trip_inserts_ten_hour_rest_when_driving_window_is_exhausted():
    plan = plan_trip(
        start_datetime=START_TIME,
        pickup_location="Austin, TX",
        dropoff_location="Phoenix, AZ",
        route=RouteSummary(distance_miles=Decimal("700"), average_speed_mph=Decimal("50")),
        current_cycle_used_hours=Decimal("0"),
    )

    rest_events = [event for event in plan.events if event.status == "off_duty"]

    assert len(rest_events) == 1
    assert rest_events[0].duration == timedelta(hours=10)
    assert plan.totals["driving_hours"] == Decimal("14.00")


def test_trip_inserts_fuel_stop_before_exceeding_one_thousand_miles_since_fuel():
    plan = plan_trip(
        start_datetime=START_TIME,
        pickup_location="Austin, TX",
        dropoff_location="Seattle, WA",
        route=RouteSummary(distance_miles=Decimal("1200"), average_speed_mph=Decimal("50")),
        current_cycle_used_hours=Decimal("0"),
    )

    fuel_events = [event for event in plan.events if event.kind == "fuel"]

    assert len(fuel_events) == 1
    assert fuel_events[0].status == "on_duty"
    assert fuel_events[0].duration == timedelta(minutes=30)
    assert fuel_events[0].distance_miles == Decimal("1000.00")


def test_daily_logs_split_events_by_calendar_date():
    plan = plan_trip(
        start_datetime=START_TIME,
        pickup_location="Austin, TX",
        dropoff_location="Seattle, WA",
        route=RouteSummary(distance_miles=Decimal("1200"), average_speed_mph=Decimal("50")),
        current_cycle_used_hours=Decimal("0"),
    )

    assert len(plan.daily_logs) >= 2
    assert plan.daily_logs[0]["date"] == "2026-05-09"
    assert plan.daily_logs[1]["date"] == "2026-05-10"
    assert all("segments" in day for day in plan.daily_logs)


def test_compliance_mode_uses_existing_daily_hours_before_rest():
    plan = plan_trip(
        start_datetime=START_TIME,
        pickup_location="Austin, TX",
        dropoff_location="Phoenix, AZ",
        route=RouteSummary(distance_miles=Decimal("500"), average_speed_mph=Decimal("50")),
        prior_8_days=[Decimal("8")] * 8,
        current_day_driving_used_hours=Decimal("10"),
        current_day_on_duty_used_hours=Decimal("12"),
    )

    assert plan.events[0].status == "on_duty"
    assert plan.events[1].status == "driving"
    assert plan.events[1].duration == timedelta(hours=1)
    assert plan.events[2].status == "off_duty"
    assert plan.events[2].duration == timedelta(hours=10)


def test_planner_inserts_cycle_restart_when_seventy_hour_cycle_is_exhausted():
    plan = plan_trip(
        start_datetime=START_TIME,
        pickup_location="Austin, TX",
        dropoff_location="Phoenix, AZ",
        route=RouteSummary(distance_miles=Decimal("200"), average_speed_mph=Decimal("50")),
        current_cycle_used_hours=Decimal("68.5"),
    )

    restart_events = [event for event in plan.events if event.kind == "cycle_restart"]

    assert len(restart_events) == 1
    assert restart_events[0].status == "off_duty"
    assert restart_events[0].duration == timedelta(hours=34)
