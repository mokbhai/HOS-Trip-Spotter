from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import serializers
from decimal import Decimal

from .planner import DEFAULT_AVERAGE_SPEED_MPH, RouteSummary, plan_trip
from .routing import RoutingServiceError, build_route
from .serializers import TripPlanRequestSerializer, TripRequestSerializer


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def validate_trip(request):
    serializer = TripRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(
        {
            "status": "valid",
            "trip": serializer.data,
            "phase": "inputs_only",
        }
    )


@api_view(["POST"])
def plan_trip_view(request):
    serializer = TripPlanRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    route_details = _resolve_route_details(data)
    route = RouteSummary(
        distance_miles=route_details["distance_miles"],
        average_speed_mph=data.get("average_speed_mph", DEFAULT_AVERAGE_SPEED_MPH),
        pickup_distance_miles=route_details["pickup_distance_miles"],
        loaded_distance_miles=route_details["loaded_distance_miles"],
    )
    plan = plan_trip(
        start_datetime=data["start_datetime"],
        current_location=data["current_location"],
        pickup_location=data["pickup_location"],
        dropoff_location=data["dropoff_location"],
        route=route,
        current_cycle_used_hours=data.get("current_cycle_used_hours"),
        prior_8_days=data.get("prior_8_days"),
        current_day_driving_used_hours=data.get("current_day_driving_used_hours"),
        current_day_on_duty_used_hours=data.get("current_day_on_duty_used_hours"),
    )

    return Response(
        {
            "status": "planned",
            "route": _serialize_route(plan.route, route_details),
            "events": [_serialize_event(event) for event in plan.events],
            "daily_logs": _serialize_daily_logs(plan.daily_logs),
            "totals": _serialize_decimal_map(plan.totals),
        }
    )


def _resolve_route_details(data):
    if "route_distance_miles" in data:
        return {
            "distance_miles": data["route_distance_miles"],
            "duration_hours": None,
            "geometry_coordinates": [],
            "instructions": [],
            "source": "manual",
            "pickup_distance_miles": 0,
            "loaded_distance_miles": data["route_distance_miles"],
        }

    try:
        route_result = build_route(
            data["current_location"],
            data["pickup_location"],
            data["dropoff_location"],
        )
    except RoutingServiceError as exc:
        raise serializers.ValidationError({"route": [str(exc)]}) from exc

    return {
        "distance_miles": route_result.distance_miles,
        "duration_hours": route_result.duration_hours,
        "geometry_coordinates": route_result.geometry_coordinates,
        "instructions": route_result.instructions,
        "source": "provider",
        "pickup_distance_miles": _pickup_leg_distance(route_result),
        "loaded_distance_miles": _loaded_leg_distance(route_result),
    }


def _pickup_leg_distance(route_result):
    if len(route_result.leg_distance_miles) >= 2:
        return route_result.leg_distance_miles[0]
    return 0


def _loaded_leg_distance(route_result):
    if len(route_result.leg_distance_miles) >= 2:
        return sum(route_result.leg_distance_miles[1:], Decimal("0"))
    return route_result.distance_miles


def _serialize_route(route, route_details):
    duration_hours = route_details["duration_hours"]
    return {
        "distance_miles": f"{route.distance_miles:.2f}",
        "average_speed_mph": f"{route.average_speed_mph:.2f}",
        "estimated_drive_hours": f"{route.estimated_drive_hours:.2f}",
        "duration_hours": None if duration_hours is None else f"{duration_hours:.2f}",
        "geometry_coordinates": route_details["geometry_coordinates"],
        "instructions": [
            {
                "text": instruction.text,
                "distance_miles": f"{instruction.distance_miles:.2f}",
                "duration_hours": f"{instruction.duration_hours:.2f}",
            }
            for instruction in route_details["instructions"]
        ],
        "source": route_details["source"],
    }


def _serialize_event(event):
    return {
        "status": event.status,
        "kind": event.kind,
        "start_time": event.start_time.isoformat(),
        "end_time": event.end_time.isoformat(),
        "duration_hours": f"{event.duration.total_seconds() / 3600:.2f}",
        "location": event.location,
        "notes": event.notes,
        "distance_miles": f"{event.distance_miles:.2f}",
    }


def _serialize_daily_logs(daily_logs):
    serialized_logs = []
    for day in daily_logs:
        serialized_logs.append(
            {
                "date": day["date"],
                "segments": [
                    {
                        **segment,
                        "duration_hours": f"{segment['duration_hours']:.2f}",
                    }
                    for segment in day["segments"]
                ],
                "paper_log": _serialize_paper_log(day["paper_log"]),
            }
        )
    return serialized_logs


def _serialize_paper_log(paper_log):
    return {
        "remarks": paper_log["remarks"],
        "brackets": paper_log["brackets"],
        "totals": _serialize_decimal_map(paper_log["totals"]),
    }


def _serialize_decimal_map(values):
    return {key: f"{value:.2f}" for key, value in values.items()}
