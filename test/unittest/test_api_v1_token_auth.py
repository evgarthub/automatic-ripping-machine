"""
Unit tests for bearer token authentication and CSRF exemption on /api/v1
"""
import datetime
import uuid

import pytest

from arm.models.notifications import Notifications
from arm.models.token import Token
from arm.models.user import User
from arm.ui import db


@pytest.fixture()
def naive_expiry_token(app):
    """A user and token whose expiry sqlite round-trips as naive"""
    with app.app_context():
        suffix = uuid.uuid4().hex
        user = User(email=f"token_test_{suffix}@example.com", password="password", hashed="hash")
        db.session.add(user)
        db.session.commit()
        token = Token(user_id=user.user_id, token_hash=f"naive-token-{suffix}", expiry_hours=24)
        db.session.add(token)
        db.session.commit()
        db.session.refresh(token)
        yield token
        db.session.delete(token)
        db.session.delete(user)
        db.session.commit()


def test_naive_expiry_token_accepted(app, naive_expiry_token):
    """
    CHECK a token whose expiry sqlite stored naive does not raise and passes require_token
    data check:
        expiry: naive
        is_expired: False
        status: 200
    """
    assert naive_expiry_token.expiry.tzinfo is None
    assert naive_expiry_token.is_expired() is False

    client = app.test_client()
    response = client.get(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {naive_expiry_token.token_hash}"},
    )
    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_expired_naive_token_returns_401(app):
    """
    CHECK a token with a naive expiry in the past is reported expired and rejected
    data check:
        expiry: naive
        is_expired: True
        status: 401
        success: False
    """
    with app.app_context():
        suffix = uuid.uuid4().hex
        user = User(email=f"expired_test_{suffix}@example.com", password="password", hashed="hash")
        db.session.add(user)
        db.session.commit()
        token = Token(user_id=user.user_id, token_hash=f"expired-token-{suffix}", expiry_hours=24)
        token.expiry = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        db.session.add(token)
        db.session.commit()

        assert token.expiry.tzinfo is None
        assert token.is_expired() is True
        token_hash = token.token_hash

    client = app.test_client()
    response = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token_hash}"})
    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_api_mutations_without_csrf_token(app, client, auth_headers):
    """
    CHECK token-authenticated PUT/DELETE/POST on /api/v1 succeed with CSRF enabled
    and no csrf_token field
    data check:
        csrf enabled: True
        PUT /notifications/<id>/read: 200
        DELETE /notifications: 200
        POST /auth/revoke: 200
    """
    assert app.config.get("WTF_CSRF_ENABLED", True)

    with app.app_context():
        notification = Notifications("Test title", "Test message")
        db.session.add(notification)
        db.session.commit()
        notification_id = notification.id

        suffix = uuid.uuid4().hex
        user = User(email=f"csrf_test_{suffix}@example.com", password="password", hashed="hash")
        db.session.add(user)
        db.session.commit()
        token = Token(user_id=user.user_id, token_hash=f"csrf-token-{suffix}", expiry_hours=24)
        db.session.add(token)
        db.session.commit()
        revoke_token_hash = token.token_hash

    put_response = client.put(f"/api/v1/notifications/{notification_id}/read", headers=auth_headers)
    assert put_response.status_code == 200

    delete_response = client.delete("/api/v1/notifications", headers=auth_headers)
    assert delete_response.status_code == 200

    post_response = client.post(
        "/api/v1/auth/revoke",
        headers={"Authorization": f"Bearer {revoke_token_hash}"},
    )
    assert post_response.status_code == 200
