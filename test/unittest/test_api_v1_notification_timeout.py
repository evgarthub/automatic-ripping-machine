"""
Unit tests for GET/PUT /api/v1/notifications/settings/timeout
"""
import pytest

from arm.models.ui_settings import UISettings
from arm.ui import db


@pytest.fixture(autouse=True)
def clean_ui_settings(app):
    """Remove all UISettings rows before and after each test"""
    with app.app_context():
        UISettings.query.delete()
        db.session.commit()
        yield
        UISettings.query.delete()
        db.session.commit()


def make_ui_settings(notify_refresh=1234):
    """Create a UISettings row like ARM setup creates"""
    row = UISettings(use_icons=True, save_remote_images=True, bootstrap_skin="bootstrap",
                     language="en", index_refresh=2000, database_limit=50,
                     notify_refresh=notify_refresh)
    db.session.add(row)
    db.session.commit()
    return row


def test_get_timeout_returns_stored_value(app, client, auth_headers):
    """
    CHECK GET returns the stored UISettings.notify_refresh value
    data check:
        status: 200
        success: True
        timeout: 1234
    """
    with app.app_context():
        make_ui_settings(notify_refresh=1234)

    response = client.get("/api/v1/notifications/settings/timeout", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["timeout"] == 1234


def test_get_timeout_defaults_without_settings_row(client, auth_headers):
    """
    CHECK GET falls back to the legacy default 6500 when no row exists
    data check:
        status: 200
        timeout: 6500
    """
    response = client.get("/api/v1/notifications/settings/timeout", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["timeout"] == 6500


def test_put_timeout_updates_stored_value(app, client, auth_headers):
    """
    CHECK PUT validates and persists a new timeout value
    data check:
        status: 200
        success: True
        timeout: 3000 persisted in UISettings.notify_refresh
    """
    with app.app_context():
        make_ui_settings(notify_refresh=1234)

    response = client.put(
        "/api/v1/notifications/settings/timeout",
        headers=auth_headers,
        json={"timeout": 3000},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["timeout"] == 3000

    with app.app_context():
        assert UISettings.query.first().notify_refresh == 3000


def test_put_timeout_rejects_non_positive(client, auth_headers):
    """
    CHECK PUT rejects zero, negative and non-integer timeouts
    data check:
        status: 400
    """
    for bad in (0, -5, "abc"):
        response = client.put(
            "/api/v1/notifications/settings/timeout",
            headers=auth_headers,
            json={"timeout": bad},
        )
        assert response.status_code == 400
        assert response.get_json()["success"] is False


def test_put_timeout_without_settings_row_returns_404(client, auth_headers):
    """
    CHECK PUT returns 404 when the UISettings row does not exist yet
    data check:
        status: 404
    """
    response = client.put(
        "/api/v1/notifications/settings/timeout",
        headers=auth_headers,
        json={"timeout": 3000},
    )
    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_timeout_requires_auth(client):
    """
    CHECK the timeout endpoints require a bearer token
    data check:
        status: 401
    """
    get_response = client.get("/api/v1/notifications/settings/timeout")
    put_response = client.put("/api/v1/notifications/settings/timeout", json={"timeout": 1})
    assert get_response.status_code == 401
    assert put_response.status_code == 401
