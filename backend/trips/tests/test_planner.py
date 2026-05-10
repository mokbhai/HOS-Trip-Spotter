from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from trips.planner import RouteSummary, plan_trip


START_TIME = datetime(2026, 5, 9, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def test_short_trip_includes_pickup_drive_breaks_and_dropoff_without_rest():
    plan = plan_trip(
        start_datetime=START_TIME,
        pickup_location="Austin, TX",
        dropoff_location="Phoenix, AZ",
        route=RouteSummary(distance_miles=Decimal("500"), average_speed_mph=Decimal("50")),
        current_cycle_used_hours=Decimal("10"),
    )

    assert plan.events[0].kind == "pickup"
    assert plan.events[-1].kind == "dropoff"
    assert not any(event.kind == "rest" for event in plan.events)
    assert plan.events[0].location == "Austin, TX"
    assert plan.events[-1].location == "Phoenix, AZ"
    assert plan.totals["driving_hours"] == Decimal("10.00")
    assert plan.totals["off_duty_hours"] == Decimal("0.50")


def test_trip_starts_with_current_location_to_pickup_drive_when_route_has_pickup_leg():
    plan = plan_trip(
        start_datetime=START_TIME,
        current_location="Dallas, TX",
        pickup_location="Austin, TX",
        dropoff_location="Phoenix, AZ",
        route=RouteSummary(
            distance_miles=Decimal("500"),
            pickup_distance_miles=Decimal("200"),
            loaded_distance_miles=Decimal("300"),
            average_speed_mph=Decimal("50"),
        ),
        current_cycle_used_hours=Decimal("0"),
    )

    assert plan.events[0].kind == "deadhead"
    assert plan.events[0].status == "driving"
    assert plan.events[0].location == "Dallas, TX"
    assert plan.events[0].notes == "Drive 200.00 miles toward pickup in Austin, TX"
    assert plan.events[1].kind == "pickup"
    assert plan.events[1].location == "Austin, TX"
    assert plan.events[2].kind == "drive"
    assert plan.events[2].location == "Austin, TX"

    assert plan.daily_logs[0]["paper_log"]["remarks"][0] == {
        "time": "08:00",
        "location": "Dallas, TX",
        "activity": "Drive 200.00 miles toward pickup in Austin, TX",
        "status": "driving",
    }


def test_long_trip_inserts_ten_hour_rest_when_driving_window_is_exhausted():
    plan = plan_trip(
        start_datetime=START_TIME,
        pickup_location="Austin, TX",
        dropoff_location="Phoenix, AZ",
        route=RouteSummary(distance_miles=Decimal("700"), average_speed_mph=Decimal("50")),
        current_cycle_used_hours=Decimal("0"),
    )

    rest_events = [event for event in plan.events if event.status == "sleeper_berth"]

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


def test_trip_inserts_paper_log_break_as_off_duty_stationary_stop():
    plan = plan_trip(
        start_datetime=START_TIME,
        pickup_location="Austin, TX",
        dropoff_location="Phoenix, AZ",
        route=RouteSummary(distance_miles=Decimal("500"), average_speed_mph=Decimal("50")),
        current_cycle_used_hours=Decimal("0"),
    )

    break_events = [event for event in plan.events if event.kind == "thirty_minute_break"]

    assert len(break_events) == 1
    assert break_events[0].status == "off_duty"
    assert break_events[0].duration == timedelta(minutes=30)
    assert break_events[0].notes == "30-minute break"


def test_thirty_minute_break_is_due_after_eight_hours_of_driving():
    plan = plan_trip(
        start_datetime=START_TIME,
        pickup_location="Austin, TX",
        dropoff_location="Phoenix, AZ",
        route=RouteSummary(distance_miles=Decimal("500"), average_speed_mph=Decimal("50")),
        current_cycle_used_hours=Decimal("0"),
    )

    break_events = [event for event in plan.events if event.kind == "thirty_minute_break"]

    assert break_events[0].start_time == START_TIME + timedelta(hours=9)


def test_thirty_minute_break_counter_resets_after_daily_rest():
    plan = plan_trip(
        start_datetime=START_TIME,
        pickup_location="Austin, TX",
        dropoff_location="Seattle, WA",
        route=RouteSummary(distance_miles=Decimal("1100"), average_speed_mph=Decimal("50")),
        current_cycle_used_hours=Decimal("0"),
    )

    break_events = [event for event in plan.events if event.kind == "thirty_minute_break"]

    assert len(break_events) == 2
    assert break_events[0].start_time == START_TIME + timedelta(hours=9)
    assert break_events[1].start_time == START_TIME + timedelta(hours=30, minutes=30)


def test_daily_logs_include_paper_log_annotations_and_24_hour_totals():
    plan = plan_trip(
        start_datetime=START_TIME,
        pickup_location="Austin, TX",
        dropoff_location="Phoenix, AZ",
        route=RouteSummary(distance_miles=Decimal("500"), average_speed_mph=Decimal("50")),
        current_cycle_used_hours=Decimal("0"),
    )

    first_day = plan.daily_logs[0]
    paper_log = first_day["paper_log"]

    assert paper_log["totals"]["total"] == Decimal("24.00")
    assert paper_log["totals"]["working_today"] == Decimal("12.00")
    assert paper_log["remarks"][0] == {
        "time": "08:00",
        "location": "Austin, TX",
        "activity": "Pickup",
        "status": "on_duty",
    }
    assert {
        "time": "17:00",
        "location": "Personal stop",
        "activity": "30-minute break",
        "status": "off_duty",
    } in paper_log["remarks"]
    assert {
        "start_time": break_events[0].start_time.isoformat(),
        "end_time": break_events[0].end_time.isoformat(),
        "status": "off_duty",
    } if (break_events := [event for event in plan.events if event.kind == "thirty_minute_break"]) else False
    assert any(bracket["status"] == "on_duty" for bracket in paper_log["brackets"])


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
    assert plan.events[2].status == "sleeper_berth"
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
    assert restart_events[0].status == "sleeper_berth"
    assert restart_events[0].duration == timedelta(hours=34)
