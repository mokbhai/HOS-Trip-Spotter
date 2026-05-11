from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import os
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import certifi


NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving"
DEFAULT_USER_AGENT = os.environ.get(
    "SPOTTER_ROUTING_USER_AGENT",
    "SpotterAssessmentRouting/1.0 (route planning integration; contact: local development)",
)
METERS_PER_MILE = Decimal("1609.344")
SECONDS_PER_HOUR = Decimal("3600")


class RoutingServiceError(Exception):
    """Base exception for external route service failures."""


class GeocodingError(RoutingServiceError):
    """Raised when a location cannot be resolved to coordinates."""


class RoutingError(RoutingServiceError):
    """Raised when OSRM cannot return a usable route."""


@dataclass(frozen=True)
class GeoPoint:
    latitude: Decimal
    longitude: Decimal

    @property
    def osrm_coordinate(self) -> str:
        return f"{self.longitude},{self.latitude}"


@dataclass(frozen=True)
class RouteInstruction:
    text: str
    distance_miles: Decimal
    duration_hours: Decimal


@dataclass(frozen=True)
class RouteResult:
    distance_miles: Decimal
    duration_hours: Decimal
    geometry_coordinates: list
    instructions: list[RouteInstruction]
    leg_distance_miles: list[Decimal] = field(default_factory=list)


def build_route(
    current_location: str,
    pickup_location: str,
    dropoff_location: str,
    *,
    fetcher=None,
    user_agent: str | None = None,
) -> RouteResult:
    fetch_json = fetcher or _fetch_json
    headers = {"User-Agent": user_agent or DEFAULT_USER_AGENT}
    geocode_cache: dict[str, GeoPoint] = {}

    points = [
        _geocode_cached(current_location, fetch_json, headers, geocode_cache),
        _geocode_cached(pickup_location, fetch_json, headers, geocode_cache),
        _geocode_cached(dropoff_location, fetch_json, headers, geocode_cache),
    ]
    route_payload = _fetch_route(points, fetch_json, headers)

    try:
        if "geometry" not in route_payload:
            raise KeyError("geometry")
        geometry = route_payload["geometry"]
        if not isinstance(geometry, dict):
            raise TypeError("route geometry must be an object")
        coordinates = geometry.get("coordinates", [])
        if not isinstance(coordinates, list):
            raise TypeError("route geometry coordinates must be a list")

        return RouteResult(
            distance_miles=_meters_to_miles(route_payload["distance"]),
            leg_distance_miles=_extract_leg_distances(route_payload),
            duration_hours=_seconds_to_hours(route_payload["duration"]),
            geometry_coordinates=coordinates,
            instructions=_extract_instructions(route_payload),
        )
    except (AttributeError, KeyError, TypeError, InvalidOperation) as exc:
        raise RoutingError("Could not build route: invalid response") from exc


def search_locations(
    query: str,
    *,
    limit: int = 5,
    fetcher=None,
    user_agent: str | None = None,
) -> list[dict]:
    normalized_query = query.strip()
    if len(normalized_query) < 3:
        return []

    fetch_json = fetcher or _fetch_json
    headers = {"User-Agent": user_agent or DEFAULT_USER_AGENT}
    safe_limit = max(1, min(limit, 10))
    url = f"{NOMINATIM_SEARCH_URL}?{urlencode({'q': normalized_query, 'format': 'jsonv2', 'limit': str(safe_limit)})}"

    try:
        payload = fetch_json(url, headers=headers)
    except Exception as exc:
        if isinstance(exc, RoutingServiceError):
            raise GeocodingError(f"Could not search locations: {exc}") from exc
        raise

    if not isinstance(payload, list):
        raise GeocodingError("Could not search locations: invalid response")

    suggestions = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            suggestions.append(
                {
                    "display_name": str(item["display_name"]),
                    "latitude": str(Decimal(str(item["lat"]))),
                    "longitude": str(Decimal(str(item["lon"]))),
                    "type": str(item.get("type") or "location"),
                    "importance": item.get("importance"),
                }
            )
        except (KeyError, InvalidOperation):
            continue
    return suggestions


def _fetch_json(url: str, *, headers: dict[str, str] | None = None):
    request = Request(url, headers=headers or {})
    try:
        with urlopen(request, timeout=20, context=_create_ssl_context()) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RoutingServiceError(str(exc)) from exc


def _create_ssl_context():
    return ssl.create_default_context(cafile=certifi.where())


def _geocode_cached(
    location: str,
    fetch_json,
    headers: dict[str, str],
    cache: dict[str, GeoPoint],
) -> GeoPoint:
    cache_key = location.strip().casefold()
    if cache_key not in cache:
        cache[cache_key] = _geocode_location(location, fetch_json, headers)
    return cache[cache_key]


def _geocode_location(location: str, fetch_json, headers: dict[str, str]) -> GeoPoint:
    query = urlencode({"q": location, "format": "jsonv2", "limit": "1"})
    url = f"{NOMINATIM_SEARCH_URL}?{query}"
    try:
        payload = fetch_json(url, headers=headers)
    except Exception as exc:
        if isinstance(exc, RoutingServiceError):
            raise GeocodingError(f"Could not geocode {location!r}: {exc}") from exc
        raise

    if not payload:
        raise GeocodingError(f"Could not geocode {location!r}")

    try:
        first_result = payload[0]
        return GeoPoint(
            latitude=Decimal(str(first_result["lat"])),
            longitude=Decimal(str(first_result["lon"])),
        )
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise GeocodingError(f"Could not geocode {location!r}: invalid response") from exc


def _fetch_route(points: list[GeoPoint], fetch_json, headers: dict[str, str]) -> dict:
    coordinate_path = quote(";".join(point.osrm_coordinate for point in points), safe=",;")
    query = urlencode({"steps": "true", "geometries": "geojson", "overview": "full"})
    url = f"{OSRM_ROUTE_URL}/{coordinate_path}?{query}"

    try:
        payload = fetch_json(url, headers=headers)
    except Exception as exc:
        if isinstance(exc, RoutingServiceError):
            raise RoutingError(f"Could not build route: {exc}") from exc
        raise

    if not isinstance(payload, dict):
        raise RoutingError("Could not build route")

    routes = payload.get("routes")
    if payload.get("code") != "Ok" or not routes:
        raise RoutingError("Could not build route")

    route = routes[0]
    if not isinstance(route, dict):
        raise RoutingError("Could not build route")

    if "distance" not in route or "duration" not in route:
        raise RoutingError("Could not build route: missing distance or duration")

    return route


def _extract_instructions(route: dict) -> list[RouteInstruction]:
    instructions = []
    if "legs" not in route:
        raise KeyError("legs")
    legs = route["legs"]
    if legs is None:
        raise TypeError("route legs must be a list")

    for leg in legs:
        if not isinstance(leg, dict):
            raise TypeError("route leg must be an object")
        steps = leg.get("steps", [])
        if steps is None:
            raise TypeError("route steps must be a list")
        for step in steps:
            if not isinstance(step, dict):
                raise TypeError("route step must be an object")
            instructions.append(
                RouteInstruction(
                    text=_format_step_text(step),
                    distance_miles=_meters_to_miles(step.get("distance", 0)),
                    duration_hours=_seconds_to_hours(step.get("duration", 0)),
                )
            )
    return instructions


def _extract_leg_distances(route: dict) -> list[Decimal]:
    if "legs" not in route:
        raise KeyError("legs")
    legs = route["legs"]
    if legs is None:
        raise TypeError("route legs must be a list")

    distances = []
    for leg in legs:
        if not isinstance(leg, dict):
            raise TypeError("route leg must be an object")
        if "distance" in leg:
            distances.append(_meters_to_miles(leg["distance"]))
        else:
            steps = leg.get("steps", [])
            if steps is None:
                raise TypeError("route steps must be a list")
            leg_distance = sum(
                (Decimal(str(step.get("distance", 0))) for step in steps if isinstance(step, dict)),
                Decimal("0"),
            )
            distances.append(_meters_to_miles(leg_distance))
    return distances


def _format_step_text(step: dict) -> str:
    maneuver = step.get("maneuver", {})
    if not isinstance(maneuver, dict):
        raise TypeError("step maneuver must be an object")

    parts = []
    step_type = str(maneuver.get("type") or "continue").replace("_", " ").title()
    modifier = maneuver.get("modifier")
    parts.append(step_type)
    if modifier:
        parts.append(str(modifier).replace("_", " "))

    name = step.get("name")
    text = " ".join(parts)
    if name:
        text = f"{text} onto {name}"
    return text


def _meters_to_miles(value) -> Decimal:
    return _quantize_decimal(Decimal(str(value)) / METERS_PER_MILE)


def _seconds_to_hours(value) -> Decimal:
    return _quantize_decimal(Decimal(str(value)) / SECONDS_PER_HOUR)


def _quantize_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
