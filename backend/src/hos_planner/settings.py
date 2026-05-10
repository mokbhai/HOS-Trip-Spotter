from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = BASE_DIR / "frontend_dist"

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
