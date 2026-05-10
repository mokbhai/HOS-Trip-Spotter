from django.conf import settings
from django.http import Http404, HttpResponse


def frontend_index(request):
    index_path = settings.FRONTEND_DIST_DIR / "index.html"
    if not index_path.exists():
        raise Http404("Frontend build not found. Run `make build` first.")

    return HttpResponse(index_path.read_text(), content_type="text/html")
