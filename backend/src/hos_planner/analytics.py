import logging
from functools import lru_cache

from django.conf import settings


logger = logging.getLogger(__name__)


@lru_cache
def _openpanel_client():
    if settings.OPENPANEL_DISABLED or not settings.OPENPANEL_CLIENT_ID or not settings.OPENPANEL_CLIENT_SECRET:
        return None

    try:
        from openpanel import OpenPanel
    except ImportError:
        logger.warning("OpenPanel package is not installed; analytics disabled.")
        return None

    return OpenPanel(
        client_id=settings.OPENPANEL_CLIENT_ID,
        client_secret=settings.OPENPANEL_CLIENT_SECRET or None,
        api_url=settings.OPENPANEL_API_URL or None,
    )


def track_event(name, properties=None):
    client = _openpanel_client()
    if client is None:
        return

    try:
        client.track(name, properties or {})
    except Exception:
        logger.exception("Failed to track OpenPanel event %s", name)
