"""
Unit tests for DELETE /api/v1/notifications
"""
import datetime

import pytest

from arm.models.notifications import Notifications
from arm.ui import db


@pytest.fixture(autouse=True)
def clean_notifications(app):
    """Remove all notifications before each test for deterministic counts"""
    with app.app_context():
        Notifications.query.delete()
        db.session.commit()
        yield


def make_notification(cleared=False):
    """Create a notification row, optionally already cleared"""
    notification = Notifications("Test title", "Test message")
    if cleared:
        notification.cleared = True
        notification.cleared_time = datetime.datetime.now()
    return notification


def test_clear_all_notifications(app, client, auth_headers):
    """
    CHECK clearing with no id mirrors legacy /notificationclose - all uncleared
    notifications are marked cleared with a cleared_time
    data check:
        status: 200
        success: True
        cleared: 3
    """
    with app.app_context():
        for _ in range(3):
            db.session.add(make_notification())
        db.session.add(make_notification(cleared=True))
        db.session.commit()

    response = client.delete("/api/v1/notifications", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["cleared"] == 3
    assert body["message"] == "Cleared 3 notifications"

    with app.app_context():
        assert Notifications.query.filter_by(cleared=False).count() == 0
        assert Notifications.query.filter_by(cleared=True).count() == 4


def test_clear_single_notification_by_id(app, client, auth_headers):
    """
    CHECK clearing with ?id=<n> clears only that notification
    data check:
        status: 200
        cleared: 1
    """
    with app.app_context():
        keep = make_notification()
        remove = make_notification()
        db.session.add(keep)
        db.session.add(remove)
        db.session.commit()
        remove_id = remove.id
        keep_id = keep.id

    response = client.delete(f"/api/v1/notifications?id={remove_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["cleared"] == 1

    with app.app_context():
        assert Notifications.query.get(remove_id).cleared is True
        assert Notifications.query.get(keep_id).cleared is False


def test_clear_single_notification_not_found(client, auth_headers):
    """
    CHECK clearing a missing notification id returns 404
    data check:
        status: 404
    """
    response = client.delete("/api/v1/notifications?id=999999", headers=auth_headers)
    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_clear_single_notification_invalid_id(client, auth_headers):
    """
    CHECK a non-numeric id returns 400
    data check:
        status: 400
    """
    response = client.delete("/api/v1/notifications?id=abc", headers=auth_headers)
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_clear_no_notifications(app, client, auth_headers):
    """
    CHECK clearing when there are no uncleared notifications reports zero
    data check:
        status: 200
        cleared: 0
        message: No notifications to clear
    """
    response = client.delete("/api/v1/notifications", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["cleared"] == 0
    assert body["message"] == "No notifications to clear"


def test_clear_notifications_requires_auth(client):
    """
    CHECK clearing notifications without a bearer token returns 401
    data check:
        status: 401
    """
    response = client.delete("/api/v1/notifications")
    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_notification_read_endpoint_untouched(app, client, auth_headers):
    """
    CHECK the existing PUT /notifications/<id>/read endpoint still works
    data check:
        status: 200
        seen: True
        dismiss_time: set
    """
    with app.app_context():
        notification = make_notification()
        db.session.add(notification)
        db.session.commit()
        notification_id = notification.id

    response = client.put(f"/api/v1/notifications/{notification_id}/read", headers=auth_headers)
    assert response.status_code == 200
    with app.app_context():
        refreshed = Notifications.query.get(notification_id)
        assert refreshed.seen is True
        assert refreshed.dismiss_time is not None
