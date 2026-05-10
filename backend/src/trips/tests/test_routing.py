from decimal import Decimal
from urllib.parse import parse_qs, unquote, urlparse
from unittest.mock import MagicMock

import pytest

from trips.services import routing
from trips.services.routing import GeocodingError, RoutingError, build_route


class FakeFetcher:
    def __init__(self, geocode_responses=None, route_response=None):
        self.geocode_responses = list(geocode_responses or [])
        self.route_response = route_response
        self.calls = []

    def __call__(self, url, *, headers=None):
        self.calls.append({"url": url, "headers": headers or {}})
        if "nominatim.openstreetmap.org" in url:
            return self.geocode_responses.pop(0)
        if "router.project-osrm.org" in url:
            return self.route_response
        raise AssertionError(f"Unexpected URL: {url}")


def test_build_route_geocodes_three_locations_and_requests_osrm_for_all_points():
    fetcher = FakeFetcher(
        geocode_responses=[
            [{"lat": "30.2672", "lon": "-97.7431"}],
            [{"lat": "32.7767", "lon": "-96.7970"}],
            [{"lat": "29.7604", "lon": "-95.3698"}],
        ],
        route_response={
            "code": "Ok",
            "routes": [
                {
                    "distance": 3218.688,
                    "duration": 7200,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [-97.7431, 30.2672],
                            [-96.7970, 32.7767],
                            [-95.3698, 29.7604],
                        ],
                    },
                    "legs": [
                        {
                            "steps": [
                                {
                                    "distance": 1000,
                                    "duration": 600,
                                    "name": "I-35",
                                    "maneuver": {"type": "depart", "modifier": "right"},
                                }
                            ]
                        },
                        {
                            "steps": [
                                {
                                    "distance": 2218.688,
                                    "duration": 6600,
                                    "name": "US-290",
                                    "maneuver": {"type": "arrive", "modifier": "left"},
                                }
                            ]
                        },
                    ],
                }
            ],
        },
    )

    route = build_route(
        "Austin, TX",
        "Dallas, TX",
        "Houston, TX",
        fetcher=fetcher,
        user_agent="spotter-tests/1.0",
    )

    geocode_calls = [
        call for call in fetcher.calls if "nominatim.openstreetmap.org" in call["url"]
    ]
    assert len(geocode_calls) == 3
    assert [parse_qs(urlparse(call["url"]).query)["q"][0] for call in geocode_calls] == [
        "Austin, TX",
        "Dallas, TX",
        "Houston, TX",
    ]
    assert all(call["headers"]["User-Agent"] == "spotter-tests/1.0" for call in geocode_calls)

    route_calls = [call for call in fetcher.calls if "router.project-osrm.org" in call["url"]]
    assert len(route_calls) == 1
    route_url = route_calls[0]["url"]
    assert "-97.7431,30.2672;-96.7970,32.7767;-95.3698,29.7604" in unquote(route_url)

    route_query = parse_qs(urlparse(route_url).query)
    assert route_query["steps"] == ["true"]
    assert route_query["geometries"] == ["geojson"]
    assert route_query["overview"] == ["full"]

    assert route.distance_miles == Decimal("2.00")
    assert route.leg_distance_miles == [Decimal("0.62"), Decimal("1.38")]
    assert route.duration_hours == Decimal("2.00")
    assert route.geometry_coordinates == [
        [-97.7431, 30.2672],
        [-96.7970, 32.7767],
        [-95.3698, 29.7604],
    ]
    assert [(step.text, step.distance_miles, step.duration_hours) for step in route.instructions] == [
        ("Depart right onto I-35", Decimal("0.62"), Decimal("0.17")),
        ("Arrive left onto US-290", Decimal("1.38"), Decimal("1.83")),
    ]


def test_build_route_reuses_geocoding_result_for_duplicate_locations():
    fetcher = FakeFetcher(
        geocode_responses=[
            [{"lat": "30.2672", "lon": "-97.7431"}],
            [{"lat": "29.7604", "lon": "-95.3698"}],
        ],
        route_response={
            "code": "Ok",
            "routes": [
                {
                    "distance": 1609.344,
                    "duration": 3600,
                    "geometry": {"type": "LineString", "coordinates": []},
                    "legs": [],
                }
            ],
        },
    )

    build_route("Austin, TX", "Austin, TX", "Houston, TX", fetcher=fetcher)

    geocode_calls = [
        call for call in fetcher.calls if "nominatim.openstreetmap.org" in call["url"]
    ]
    assert len(geocode_calls) == 2


def test_build_route_raises_geocoding_error_when_location_is_not_found():
    fetcher = FakeFetcher(geocode_responses=[[]])

    with pytest.raises(GeocodingError, match="Could not geocode"):
        build_route("Unknown place", "Dallas, TX", "Houston, TX", fetcher=fetcher)


def test_fetch_json_uses_certifi_backed_ssl_context(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = None
    urlopen = MagicMock(return_value=response)
    ssl_context = object()

    monkeypatch.setattr(routing, "urlopen", urlopen)
    monkeypatch.setattr(routing, "json", MagicMock(load=MagicMock(return_value={"ok": True})))
    monkeypatch.setattr(routing, "_create_ssl_context", MagicMock(return_value=ssl_context))

    assert routing._fetch_json("https://example.test", headers={"User-Agent": "test"}) == {"ok": True}
    assert urlopen.call_args.kwargs["context"] is ssl_context


@pytest.mark.parametrize(
    "route_response",
    [
        {"code": "NoRoute", "routes": []},
        {"code": "Ok", "routes": []},
        {"code": "Ok"},
        [],
        {"code": "Ok", "routes": [{"distance": "bad", "duration": 7200}]},
        {"code": "Ok", "routes": [{"distance": 1000, "duration": None}]},
        {"code": "Ok", "routes": [{"distance": 1000, "duration": 7200}]},
        {
            "code": "Ok",
            "routes": [
                {
                    "distance": 1000,
                    "duration": 7200,
                    "geometry": {"type": "LineString", "coordinates": []},
                }
            ],
        },
        {"code": "Ok", "routes": [{"distance": 1000, "duration": 7200, "geometry": None}]},
        {"code": "Ok", "routes": [{"distance": 1000, "duration": 7200, "legs": None}]},
        {"code": "Ok", "routes": [None]},
        {
            "code": "Ok",
            "routes": [
                {
                    "distance": 1000,
                    "duration": 7200,
                    "geometry": {"type": "LineString", "coordinates": []},
                    "legs": [{"steps": [{"distance": 100, "duration": 60, "maneuver": "bad"}]}],
                }
            ],
        },
        {
            "code": "Ok",
            "routes": [
                {
                    "distance": 1000,
                    "duration": 7200,
                    "geometry": {"type": "LineString", "coordinates": []},
                    "legs": [{"steps": [{"distance": 100, "duration": 60, "maneuver": []}]}],
                }
            ],
        },
    ],
)
def test_build_route_raises_routing_error_when_osrm_does_not_return_a_route(route_response):
    fetcher = FakeFetcher(
        geocode_responses=[
            [{"lat": "30.2672", "lon": "-97.7431"}],
            [{"lat": "32.7767", "lon": "-96.7970"}],
            [{"lat": "29.7604", "lon": "-95.3698"}],
        ],
        route_response=route_response,
    )

    with pytest.raises(RoutingError, match="Could not build route"):
        build_route("Austin, TX", "Dallas, TX", "Houston, TX", fetcher=fetcher)
