from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP


MAX_DAILY_DRIVING_HOURS = Decimal("11")
MAX_DAILY_ON_DUTY_HOURS = Decimal("14")
MAX_CYCLE_HOURS = Decimal("70")
REST_RESET_HOURS = Decimal("10")
CYCLE_RESTART_HOURS = Decimal("34")
PICKUP_HOURS = Decimal("1")
DROPOFF_HOURS = Decimal("1")
FUEL_INTERVAL_MILES = Decimal("1000")
FUEL_STOP_HOURS = Decimal("0.5")
THIRTY_MINUTE_BREAK_AFTER_DRIVING_HOURS = Decimal("8")
THIRTY_MINUTE_BREAK_HOURS = Decimal("0.5")
DEFAULT_AVERAGE_SPEED_MPH = Decimal("55")


@dataclass(frozen=True)
class RouteSummary:
    distance_miles: Decimal
    average_speed_mph: Decimal = DEFAULT_AVERAGE_SPEED_MPH
    pickup_distance_miles: Decimal = Decimal("0")
    loaded_distance_miles: Decimal | None = None

    @property
    def estimated_drive_hours(self) -> Decimal:
        return _quantize_hours(self.distance_miles / self.average_speed_mph)

    @property
    def remaining_loaded_distance_miles(self) -> Decimal:
        if self.loaded_distance_miles is not None:
            return self.loaded_distance_miles
        return self.distance_miles - self.pickup_distance_miles


@dataclass(frozen=True)
class DutyEvent:
    status: str
    kind: str
    start_time: datetime
    end_time: datetime
    location: str
    notes: str
    distance_miles: Decimal = Decimal("0")

    @property
    def duration(self) -> timedelta:
        return self.end_time - self.start_time


@dataclass(frozen=True)
class TripPlan:
    route: RouteSummary
    events: list[DutyEvent]
    daily_logs: list[dict]
    totals: dict[str, Decimal]


@dataclass
class _Clock:
    current_time: datetime
    driving_used_today: Decimal
    on_duty_used_today: Decimal
    cycle_used: Decimal
    remaining_distance: Decimal
    miles_since_fuel: Decimal = Decimal("0")
    driving_since_last_break: Decimal = Decimal("0")


def plan_trip(
    *,
    start_datetime: datetime,
    pickup_location: str,
    dropoff_location: str,
    route: RouteSummary,
    current_location: str | None = None,
    current_cycle_used_hours: Decimal | None = None,
    prior_8_days: list[Decimal] | None = None,
    current_day_driving_used_hours: Decimal | None = None,
    current_day_on_duty_used_hours: Decimal | None = None,
) -> TripPlan:
    cycle_used = _initial_cycle_used(current_cycle_used_hours, prior_8_days)
    clock = _Clock(
        current_time=start_datetime,
        driving_used_today=current_day_driving_used_hours or Decimal("0"),
        on_duty_used_today=current_day_on_duty_used_hours or Decimal("0"),
        cycle_used=cycle_used,
        remaining_distance=route.remaining_loaded_distance_miles,
        driving_since_last_break=current_day_driving_used_hours or Decimal("0"),
    )
    events: list[DutyEvent] = []

    if current_location and route.pickup_distance_miles > 0:
        deadhead_hours = _quantize_hours(route.pickup_distance_miles / route.average_speed_mph)
        _append_driving_event(
            events,
            clock,
            deadhead_hours,
            route.pickup_distance_miles,
            current_location,
            f"Drive {_quantize_miles(route.pickup_distance_miles)} miles toward pickup in {pickup_location}",
            kind="deadhead",
            count_toward_remaining=False,
        )

    _append_on_duty_event(events, clock, PICKUP_HOURS, pickup_location, "pickup", "Pickup")

    while clock.remaining_distance > 0:
        if _cycle_remaining(clock) <= 0:
            _append_cycle_restart_event(events, clock, pickup_location)
            continue

        if _daily_driving_remaining(clock) <= 0 or _daily_on_duty_remaining(clock) <= 0:
            _append_rest_event(events, clock, pickup_location)
            continue

        distance_until_fuel = FUEL_INTERVAL_MILES - clock.miles_since_fuel
        drive_hours_until_fuel = distance_until_fuel / route.average_speed_mph
        drive_hours_until_destination = clock.remaining_distance / route.average_speed_mph
        drive_hours_until_break = _hours_until_thirty_minute_break(clock)
        drive_hours = min(
            _daily_driving_remaining(clock),
            _daily_on_duty_remaining(clock),
            _cycle_remaining(clock),
            drive_hours_until_fuel,
            drive_hours_until_destination,
            drive_hours_until_break,
        )

        if drive_hours <= 0:
            if clock.remaining_distance > 0 and clock.miles_since_fuel >= FUEL_INTERVAL_MILES:
                _append_fuel_event(events, clock)
            else:
                _append_thirty_minute_break_event(events, clock)
            continue

        miles = _quantize_miles(drive_hours * route.average_speed_mph)
        if miles > clock.remaining_distance:
            miles = clock.remaining_distance

        actual_hours = _quantize_hours(miles / route.average_speed_mph)
        _append_driving_event(
            events,
            clock,
            actual_hours,
            miles,
            _event_end_location(events, pickup_location),
            f"Drive {miles} miles toward {dropoff_location}",
        )

        if clock.remaining_distance > 0 and clock.miles_since_fuel >= FUEL_INTERVAL_MILES:
            if _daily_on_duty_remaining(clock) < FUEL_STOP_HOURS:
                _append_rest_event(events, clock, pickup_location)
            _append_fuel_event(events, clock)
        elif clock.remaining_distance > 0 and _thirty_minute_break_due(clock):
            _append_thirty_minute_break_event(events, clock)

    _append_on_duty_event(events, clock, DROPOFF_HOURS, dropoff_location, "dropoff", "Drop-off")

    return TripPlan(
        route=route,
        events=events,
        daily_logs=_build_daily_logs(events),
        totals=_calculate_totals(events),
    )


def _append_on_duty_event(
    events: list[DutyEvent],
    clock: _Clock,
    hours: Decimal,
    location: str,
    kind: str,
    notes: str,
) -> None:
    if _cycle_remaining(clock) < hours:
        _append_cycle_restart_event(events, clock, location)

    if _daily_on_duty_remaining(clock) < hours:
        _append_rest_event(events, clock, location)

    start_time = clock.current_time
    end_time = start_time + _hours_to_timedelta(hours)
    events.append(
        DutyEvent(
            status="on_duty",
            kind=kind,
            start_time=start_time,
            end_time=end_time,
            location=location,
            notes=notes,
        )
    )
    clock.current_time = end_time
    clock.on_duty_used_today += hours
    clock.cycle_used += hours
    if hours >= THIRTY_MINUTE_BREAK_HOURS:
        clock.driving_since_last_break = Decimal("0")


def _append_driving_event(
    events: list[DutyEvent],
    clock: _Clock,
    hours: Decimal,
    miles: Decimal,
    location: str,
    notes: str,
    *,
    kind: str = "drive",
    count_toward_remaining: bool = True,
) -> None:
    start_time = clock.current_time
    end_time = start_time + _hours_to_timedelta(hours)
    events.append(
        DutyEvent(
            status="driving",
            kind=kind,
            start_time=start_time,
            end_time=end_time,
            location=location,
            notes=notes,
            distance_miles=miles,
        )
    )
    clock.current_time = end_time
    clock.driving_used_today += hours
    clock.on_duty_used_today += hours
    clock.cycle_used += hours
    if count_toward_remaining:
        clock.remaining_distance -= miles
    clock.miles_since_fuel += miles
    clock.driving_since_last_break += hours


def _append_rest_event(events: list[DutyEvent], clock: _Clock, location: str) -> None:
    hours = REST_RESET_HOURS
    start_time = clock.current_time
    end_time = start_time + _hours_to_timedelta(hours)
    events.append(
        DutyEvent(
            status="sleeper_berth",
            kind="rest",
            start_time=start_time,
            end_time=end_time,
            location=location,
            notes="10-hour sleeper berth reset",
        )
    )
    clock.current_time = end_time
    clock.driving_used_today = Decimal("0")
    clock.on_duty_used_today = Decimal("0")
    clock.driving_since_last_break = Decimal("0")


def _append_cycle_restart_event(events: list[DutyEvent], clock: _Clock, location: str) -> None:
    start_time = clock.current_time
    end_time = start_time + _hours_to_timedelta(CYCLE_RESTART_HOURS)
    events.append(
        DutyEvent(
            status="sleeper_berth",
            kind="cycle_restart",
            start_time=start_time,
            end_time=end_time,
            location=location,
            notes="34-hour sleeper berth cycle restart",
        )
    )
    clock.current_time = end_time
    clock.driving_used_today = Decimal("0")
    clock.on_duty_used_today = Decimal("0")
    clock.cycle_used = Decimal("0")
    clock.driving_since_last_break = Decimal("0")


def _append_fuel_event(events: list[DutyEvent], clock: _Clock) -> None:
    if _cycle_remaining(clock) < FUEL_STOP_HOURS:
        _append_cycle_restart_event(events, clock, "Fuel stop")

    start_time = clock.current_time
    end_time = start_time + _hours_to_timedelta(FUEL_STOP_HOURS)
    events.append(
        DutyEvent(
            status="on_duty",
            kind="fuel",
            start_time=start_time,
            end_time=end_time,
            location="Fuel stop",
            notes="Fuel stop",
            distance_miles=_quantize_miles(clock.miles_since_fuel),
        )
    )
    clock.current_time = end_time
    clock.on_duty_used_today += FUEL_STOP_HOURS
    clock.cycle_used += FUEL_STOP_HOURS
    clock.miles_since_fuel = Decimal("0")
    clock.driving_since_last_break = Decimal("0")


def _append_thirty_minute_break_event(events: list[DutyEvent], clock: _Clock) -> None:
    start_time = clock.current_time
    end_time = start_time + _hours_to_timedelta(THIRTY_MINUTE_BREAK_HOURS)
    events.append(
        DutyEvent(
            status="off_duty",
            kind="thirty_minute_break",
            start_time=start_time,
            end_time=end_time,
            location="Personal stop",
            notes="30-minute break",
        )
    )
    clock.current_time = end_time
    clock.driving_since_last_break = Decimal("0")


def _event_end_location(events: list[DutyEvent], fallback: str) -> str:
    if not events:
        return fallback

    previous = events[-1]
    if previous.status == "driving":
        return "En route"
    return previous.location or fallback


def _build_daily_logs(events: list[DutyEvent]) -> list[dict]:
    logs: dict[str, list[dict]] = {}
    for event in events:
        for segment_start, segment_end in _split_by_date(event.start_time, event.end_time):
            date_key = segment_start.date().isoformat()
            logs.setdefault(date_key, []).append(
                {
                    "status": event.status,
                    "kind": event.kind,
                    "start_time": segment_start.isoformat(),
                    "end_time": segment_end.isoformat(),
                    "duration_hours": _quantize_hours(
                        Decimal((segment_end - segment_start).total_seconds()) / Decimal("3600")
                    ),
                    "location": event.location,
                    "notes": event.notes,
                }
            )

    return [
        {
            "date": date,
            "segments": segments,
            "paper_log": _build_paper_log(date, segments),
        }
        for date, segments in sorted(logs.items())
    ]


def _build_paper_log(date: str, segments: list[dict]) -> dict:
    completed_segments = _complete_day_segments(date, segments)
    return {
        "remarks": [_paper_log_remark(segment) for segment in segments],
        "brackets": [_paper_log_bracket(segment) for segment in segments if _should_bracket(segment)],
        "totals": _paper_log_totals(completed_segments),
    }


def _paper_log_remark(segment: dict) -> dict:
    return {
        "time": segment["start_time"][11:16],
        "location": segment["location"],
        "activity": segment["notes"],
        "status": segment["status"],
    }


def _paper_log_bracket(segment: dict) -> dict:
    return {
        "start_time": segment["start_time"],
        "end_time": segment["end_time"],
        "status": segment["status"],
    }


def _should_bracket(segment: dict) -> bool:
    if segment["status"] == "driving":
        return False
    if segment["kind"] in {"rest", "cycle_restart"}:
        return False
    return _minute_in_day(segment["end_time"], segment["start_time"][:10]) > _minute_in_day(
        segment["start_time"],
        segment["start_time"][:10],
    )


def _complete_day_segments(date: str, segments: list[dict]) -> list[dict]:
    completed: list[dict] = []
    cursor_minutes = 0

    for segment in sorted(segments, key=lambda item: item["start_time"]):
        start_minutes = _minute_in_day(segment["start_time"], date)
        end_minutes = _minute_in_day(segment["end_time"], date)
        if start_minutes > cursor_minutes:
            completed.append(_paper_log_gap(date, cursor_minutes, start_minutes))
        completed.append(segment)
        cursor_minutes = max(cursor_minutes, end_minutes)

    if cursor_minutes < 24 * 60:
        completed.append(_paper_log_gap(date, cursor_minutes, 24 * 60))

    return completed


def _paper_log_gap(date: str, start_minutes: int, end_minutes: int) -> dict:
    return {
        "status": "off_duty",
        "kind": "off_duty_gap",
        "start_time": _time_for_minute(date, start_minutes),
        "end_time": _time_for_minute(date, end_minutes),
        "duration_hours": _quantize_hours(Decimal(end_minutes - start_minutes) / Decimal("60")),
        "location": "",
        "notes": "Off-duty time not otherwise assigned",
    }


def _paper_log_totals(segments: list[dict]) -> dict[str, Decimal]:
    totals = {
        "off_duty": Decimal("0"),
        "sleeper_berth": Decimal("0"),
        "driving": Decimal("0"),
        "on_duty": Decimal("0"),
    }
    for segment in segments:
        totals[segment["status"]] += segment["duration_hours"]

    totals = {key: _quantize_hours(value) for key, value in totals.items()}
    totals["total"] = _quantize_hours(sum(totals.values(), Decimal("0")))
    totals["working_today"] = _quantize_hours(totals["driving"] + totals["on_duty"])
    return totals


def _minute_in_day(value: str, date: str) -> int:
    segment_date = value[:10]
    if segment_date < date:
        return 0
    if segment_date > date:
        return 24 * 60
    return min(int(value[11:13]) * 60 + int(value[14:16]), 24 * 60)


def _time_for_minute(date: str, total_minutes: int) -> str:
    clamped_minutes = max(0, min(total_minutes, 24 * 60))
    hour = clamped_minutes // 60
    minute = clamped_minutes % 60
    return f"{date}T{hour:02d}:{minute:02d}:00"


def _split_by_date(start_time: datetime, end_time: datetime):
    cursor = start_time
    while cursor < end_time:
        next_midnight = datetime.combine(
            cursor.date() + timedelta(days=1),
            time.min,
            tzinfo=cursor.tzinfo,
        )
        segment_end = min(end_time, next_midnight)
        yield cursor, segment_end
        cursor = segment_end


def _calculate_totals(events: list[DutyEvent]) -> dict[str, Decimal]:
    totals = {
        "driving_hours": Decimal("0"),
        "on_duty_hours": Decimal("0"),
        "off_duty_hours": Decimal("0"),
        "distance_miles": Decimal("0"),
    }
    for event in events:
        hours = _quantize_hours(Decimal(event.duration.total_seconds()) / Decimal("3600"))
        if event.status == "driving":
            totals["driving_hours"] += hours
            totals["distance_miles"] += event.distance_miles
        elif event.status == "on_duty":
            totals["on_duty_hours"] += hours
        elif event.status == "off_duty":
            totals["off_duty_hours"] += hours
        elif event.status == "sleeper_berth":
            totals["off_duty_hours"] += hours

    return {key: _quantize_hours(value) for key, value in totals.items()}


def _initial_cycle_used(
    current_cycle_used_hours: Decimal | None,
    prior_8_days: list[Decimal] | None,
) -> Decimal:
    if prior_8_days is not None:
        return sum(prior_8_days, Decimal("0"))
    return current_cycle_used_hours or Decimal("0")


def _daily_driving_remaining(clock: _Clock) -> Decimal:
    return max(Decimal("0"), MAX_DAILY_DRIVING_HOURS - clock.driving_used_today)


def _daily_on_duty_remaining(clock: _Clock) -> Decimal:
    return max(Decimal("0"), MAX_DAILY_ON_DUTY_HOURS - clock.on_duty_used_today)


def _cycle_remaining(clock: _Clock) -> Decimal:
    return max(Decimal("0"), MAX_CYCLE_HOURS - clock.cycle_used)


def _hours_until_thirty_minute_break(clock: _Clock) -> Decimal:
    return max(
        Decimal("0"),
        THIRTY_MINUTE_BREAK_AFTER_DRIVING_HOURS - clock.driving_since_last_break,
    )


def _thirty_minute_break_due(clock: _Clock) -> bool:
    return clock.driving_since_last_break >= THIRTY_MINUTE_BREAK_AFTER_DRIVING_HOURS


def _hours_to_timedelta(hours: Decimal) -> timedelta:
    return timedelta(minutes=float(hours * Decimal("60")))


def _quantize_hours(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _quantize_miles(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
