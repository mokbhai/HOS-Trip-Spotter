import pytest


@pytest.mark.django_db
def test_root_serves_built_frontend_index(client, settings, tmp_path):
    frontend_dist = tmp_path / "frontend_dist"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<!doctype html><div id='root'></div>")
    settings.FRONTEND_DIST_DIR = frontend_dist

    response = client.get("/")

    assert response.status_code == 200
    assert b"<div id='root'></div>" in response.content


@pytest.mark.django_db
def test_frontend_fallback_does_not_shadow_api(client):
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
