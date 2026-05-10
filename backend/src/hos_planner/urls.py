from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path, re_path

from .views import frontend_index


urlpatterns = [
    path("api/", include("trips.api.urls")),
    path("", frontend_index, name="frontend-index"),
    re_path(r"^(?!api/|static/).*$", frontend_index, name="frontend-fallback"),
]

urlpatterns += staticfiles_urlpatterns()
