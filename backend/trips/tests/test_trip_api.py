import pytest
from decimal import Decimal
from rest_framework.test import APIClient

from trips.routing import RouteInstruction, RouteResult, RoutingError
from trips.serializers import TripRequestSerializer


VALID_QUICK_DATA = {
    "current_location": "  Dallas, TX  ",
    "pickup_location": "Austin, TX",
    "dropoff_location": "Phoenix, AZ",
    "start_datetime": "2026-05-09T08:00:00+05:30",
    "hos_mode": "quick",
    "current_cycle_used_hours": "12.50",
}


INVALID_COMPLIANCE_DATA = {
    "current_location": "Dallas, TX",
    "pickup_location": "Austin, TX",
    "dropoff_location": "Phoenix, AZ",
    "start_datetime": "2026-05-09T08:00:00+05:30",
    "hos_mode": "compliance",
    "prior_8_days": ["8", "9.5", "7", "0", "10", "11", "6.25", "8"],
    "current_duty_status": "off_duty",
    "current_day_driving_used_hours": "8",
    "current_day_on_duty_used_hours": "7",
}


@pytest.mark.django_db
def test_health_returns_ok():
    response = APIClient().get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_validate_trip_returns_normalized_quick_mode_data():
    serializer = TripRequestSerializer(data=VALID_QUICK_DATA)
    serializer.is_valid(raise_exception=True)

    response = APIClient().post(
        "/api/trips/validate/",
        VALID_QUICK_DATA,
        format="json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "valid",
        "phase": "inputs_only",
        "trip": serializer.data,
    }


@pytest.mark.django_db
def test_validate_trip_returns_field_errors_for_invalid_compliance_mode():
    response = APIClient().post(
        "/api/trips/validate/",
        INVALID_COMPLIANCE_DATA,
        format="json",
    )

    assert response.status_code == 400
    body = response.json()
    assert "current_day_driving_used_hours" in body
    assert (
        "cannot exceed current_day_on_duty_used_hours"
        in body["current_day_driving_used_hours"][0]
    )


@pytest.mark.django_db
def test_plan_trip_returns_route_events_and_daily_logs():
    response = APIClient().post(
        "/api/trips/plan/",
        {
            **VALID_QUICK_DATA,
            "route_distance_miles": "700",
            "average_speed_mph": "50",
        },
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "planned"
    assert body["route"]["distance_miles"] == "700.00"
    assert body["totals"]["driving_hours"] == "14.00"
    assert [event["status"] for event in body["events"]].count("off_duty") == 1
    assert body["daily_logs"]
    assert body["daily_logs"][0]["paper_log"]["totals"]["total"] == "24.00"
    assert body["daily_logs"][0]["paper_log"]["remarks"][0]["activity"] == "Pickup"
    assert body["daily_logs"][0]["paper_log"]["brackets"]


@pytest.mark.django_db
def test_plan_trip_allows_route_distance_override_without_calling_provider(monkeypatch):
    def fail_if_called(current_location, pickup_location, dropoff_location):
        raise AssertionError("route provider should not be called when distance is supplied")

    monkeypatch.setattr("trips.views.build_route", fail_if_called)

    response = APIClient().post(
        "/api/trips/plan/",
        {
            **VALID_QUICK_DATA,
            "route_distance_miles": "700",
            "average_speed_mph": "50",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["route"]["source"] == "manual"


@pytest.mark.django_db
def test_plan_trip_uses_routing_service_when_distance_is_not_provided(monkeypatch):
    def fake_build_route(current_location, pickup_location, dropoff_location):
        assert current_location == "Dallas, TX"
        assert pickup_location == "Austin, TX"
        assert dropoff_location == "Phoenix, AZ"
        return RouteResult(
            distance_miles=Decimal("700.00"),
            leg_distance_miles=[Decimal("200.00"), Decimal("500.00")],
            duration_hours=Decimal("14.00"),
            geometry_coordinates=[[-96.7970, 32.7767], [-97.7431, 30.2672]],
            instructions=[
                RouteInstruction(
                    text="Depart onto I-35",
                    distance_miles=Decimal("25.00"),
                    duration_hours=Decimal("0.50"),
                )
            ],
        )

    monkeypatch.setattr("trips.views.build_route", fake_build_route)

    response = APIClient().post(
        "/api/trips/plan/",
        VALID_QUICK_DATA,
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "planned"
    assert body["route"]["distance_miles"] == "700.00"
    assert body["events"][0]["kind"] == "deadhead"
    assert body["events"][0]["location"] == "Dallas, TX"
    assert body["events"][1]["kind"] == "pickup"
    assert body["daily_logs"][0]["paper_log"]["remarks"][0]["location"] == "Dallas, TX"
    assert body["route"]["duration_hours"] == "14.00"
    assert body["route"]["geometry_coordinates"] == [[-96.797, 32.7767], [-97.7431, 30.2672]]
    assert body["route"]["instructions"] == [
        {
            "text": "Depart onto I-35",
            "distance_miles": "25.00",
            "duration_hours": "0.50",
        }
    ]


@pytest.mark.django_db
def test_plan_trip_returns_400_when_routing_service_fails(monkeypatch):
    def fake_build_route(current_location, pickup_location, dropoff_location):
        raise RoutingError("Could not build route")

    monkeypatch.setattr("trips.views.build_route", fake_build_route)

    response = APIClient().post(
        "/api/trips/plan/",
        VALID_QUICK_DATA,
        format="json",
    )

    assert response.status_code == 400
    assert "route" in response.json()
