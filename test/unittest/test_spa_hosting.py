"""
Unit tests for hosting the built React SPA under the /app/ URL prefix
"""
import pytest

from arm.ui.spa import SPA_DIR_ENV, SPA_MISSING_HINT


@pytest.fixture()
def spa_dist(tmp_path, monkeypatch):
    """Temporary SPA build directory with an index.html and one asset"""
    assets = tmp_path / "assets"
    assets.mkdir()
    (tmp_path / "index.html").write_text("<html>spa index</html>", encoding="utf-8")
    (assets / "test.txt").write_text("asset body", encoding="utf-8")
    monkeypatch.setenv(SPA_DIR_ENV, str(tmp_path))
    return tmp_path


def test_index_served_at_app_root(client, spa_dist):
    """
    CHECK /app/ serves index.html uncached
    data check:
        status: 200
        cache-control: no-store
    """
    response = client.get("/app/")
    assert response.status_code == 200
    assert b"spa index" in response.data
    assert response.headers["Cache-Control"] == "no-store"


def test_asset_served_with_long_cache(client, spa_dist):
    """
    CHECK a hashed asset is served with an immutable long cache header
    data check:
        status: 200
        cache-control: public, max-age=31536000, immutable
    """
    response = client.get("/app/assets/test.txt")
    assert response.status_code == 200
    assert response.data == b"asset body"
    assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"


def test_deep_link_falls_back_to_index(client, spa_dist):
    """
    CHECK an unknown deep link falls back to index.html for client-side routing
    data check:
        status: 200
        body: index.html
    """
    response = client.get("/app/jobs/5")
    assert response.status_code == 200
    assert b"spa index" in response.data
    assert response.headers["Cache-Control"] == "no-store"


def test_missing_dist_returns_hint(client, tmp_path, monkeypatch):
    """
    CHECK a missing SPA build yields a 404 hint instead of crashing the UI
    data check:
        status: 404
        body: SPA build not found
    """
    monkeypatch.setenv(SPA_DIR_ENV, str(tmp_path / "nonexistent"))
    response = client.get("/app/")
    assert response.status_code == 404
    assert response.mimetype == "text/plain"
    assert SPA_MISSING_HINT in response.get_data(as_text=True)


def test_traversal_cannot_escape_dist(client, spa_dist):
    """
    CHECK a traversal path below /app/ never serves files outside the dist dir
    data check:
        status: 200
        body: index.html fallback
    """
    response = client.get("/app/..%2F..%2F..%2Fetc%2Fpasswd")
    assert response.status_code == 200
    assert b"spa index" in response.data


def test_legacy_route_still_served(client, spa_dist):
    """
    CHECK the legacy Jinja UI keeps working (login page) with the SPA mounted
    data check:
        status: 200
        body: not the SPA
    """
    response = client.get("/login")
    assert response.status_code == 200
    assert SPA_MISSING_HINT not in response.get_data(as_text=True)


def test_api_v1_jobs_not_shadowed(client, spa_dist):
    """
    CHECK /api/v1/jobs still answers as JSON API and is not caught by the SPA
    data check:
        status: 401
        success: False
    """
    response = client.get("/api/v1/jobs")
    assert response.status_code == 401
    assert response.get_json()["success"] is False
