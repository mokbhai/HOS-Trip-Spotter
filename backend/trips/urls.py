from django.urls import path

from .views import health, plan_trip_view, validate_trip


urlpatterns = [
    path("health/", health, name="health"),
    path("trips/plan/", plan_trip_view, name="plan-trip"),
    path("trips/validate/", validate_trip, name="validate-trip"),
]
