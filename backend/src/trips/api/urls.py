from django.urls import path

from .views import health, plan_trip_view, search_locations_view, validate_trip


urlpatterns = [
    path("health/", health, name="health"),
    path("locations/search/", search_locations_view, name="search-locations"),
    path("trips/plan/", plan_trip_view, name="plan-trip"),
    path("trips/validate/", validate_trip, name="validate-trip"),
]
