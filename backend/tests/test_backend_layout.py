import importlib.util

from django.conf import settings


def test_backend_packages_are_loaded_from_src_layout():
    trips_spec = importlib.util.find_spec("trips")
    project_spec = importlib.util.find_spec("hos_planner")

    assert trips_spec is not None
    assert project_spec is not None
    assert "/src/trips/" in trips_spec.origin
    assert "/src/hos_planner/" in project_spec.origin


def test_trips_app_uses_api_and_services_packages():
    api_views_spec = importlib.util.find_spec("trips.api.views")
    api_serializers_spec = importlib.util.find_spec("trips.api.serializers")
    services_planner_spec = importlib.util.find_spec("trips.services.planner")
    services_routing_spec = importlib.util.find_spec("trips.services.routing")

    assert api_views_spec is not None
    assert api_serializers_spec is not None
    assert services_planner_spec is not None
    assert services_routing_spec is not None


def test_backend_base_dir_still_points_to_backend_root():
    assert settings.BASE_DIR.name == "backend"
    assert settings.FRONTEND_DIST_DIR == settings.BASE_DIR / "frontend_dist"
