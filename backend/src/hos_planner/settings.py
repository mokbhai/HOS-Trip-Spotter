import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_DIST_DIR = BASE_DIR / "frontend_dist"


def _load_env_file(path):
    if not path.exists():
        return

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_env_file(PROJECT_ROOT / ".env")

SECRET_KEY = "dev-only"

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "trips",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "hos_planner.middleware.OpenPanelAPIMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "hos_planner.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

STATIC_URL = "static/"
STATICFILES_DIRS = [
    ("frontend", FRONTEND_DIST_DIR),
]

REST_FRAMEWORK = {
    "UNAUTHENTICATED_USER": None,
}

OPENPANEL_CLIENT_ID = os.environ.get("OPENPANEL_CLIENT_ID", "")
OPENPANEL_CLIENT_SECRET = os.environ.get("OPENPANEL_CLIENT_SECRET", "")
OPENPANEL_API_URL = os.environ.get("OPENPANEL_API_URL", "https://api.openpanel.dev")
OPENPANEL_DISABLED = os.environ.get("OPENPANEL_DISABLED", "").lower() in {"1", "true", "yes"} or any(
    "pytest" in argument for argument in sys.argv
)
