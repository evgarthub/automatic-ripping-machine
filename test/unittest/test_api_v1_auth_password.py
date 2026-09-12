"""
Unit tests for PUT /api/v1/auth/password
"""
import uuid

import bcrypt
import pytest

from arm.models.token import Token
from arm.models.user import User
from arm.ui import db


@pytest.fixture()
def password_user(app):
    """A user with a real legacy-style bcrypt hash and two API tokens"""
    with app.app_context():
        suffix = uuid.uuid4().hex
        salt = bcrypt.gensalt()
        user = User(email=f"password_test_{suffix}@example.com",
                    password=bcrypt.hashpw("OldPass123".encode("utf-8"), salt),
                    hashed=salt)
        db.session.add(user)
        db.session.commit()
        tokens = []
        for _ in range(2):
            token = Token(user_id=user.user_id, token_hash=f"pw-token-{suffix}-{uuid.uuid4().hex}",
                          expiry_hours=24)
            db.session.add(token)
            tokens.append(token)
        db.session.commit()
        yield user
        Token.query.filter_by(user_id=user.user_id).delete()
        if User.query.get(user.user_id) is not None:
            db.session.delete(user)
        db.session.commit()


def password_headers(token_hash):
    """Bearer headers for a given token hash"""
    return {"Authorization": f"Bearer {token_hash}"}


def test_update_password_success(app, client, password_user):
    """
    CHECK a happy password change mirrors the legacy scheme and revokes tokens
    data check:
        status: 200
        success: True
        user.password: bcrypt of the new password with the same salt
        all user tokens: deleted
    """
    with app.app_context():
        token_hash = Token.query.filter_by(user_id=password_user.user_id).first().token_hash
        user_id = password_user.user_id
        salt = password_user.hash

    response = client.put(
        "/api/v1/auth/password",
        headers=password_headers(token_hash),
        json={"current_password": "OldPass123", "new_password": "NewPass456"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert "updated" in body["message"].lower()

    with app.app_context():
        refreshed = User.query.get(user_id)
        assert refreshed.password == bcrypt.hashpw(b"NewPass456", salt)
        assert refreshed.hash == salt
        assert Token.query.filter_by(user_id=user_id).count() == 0


def test_update_password_wrong_current_returns_400(app, client, password_user):
    """
    CHECK a wrong current password is rejected and nothing changes
    data check:
        status: 400
        success: False
        user.password: unchanged
        tokens: still present
    """
    with app.app_context():
        token_hash = Token.query.filter_by(user_id=password_user.user_id).first().token_hash
        user_id = password_user.user_id
        original_password = password_user.password

    response = client.put(
        "/api/v1/auth/password",
        headers=password_headers(token_hash),
        json={"current_password": "WrongPass", "new_password": "NewPass456"},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False

    with app.app_context():
        refreshed = User.query.get(user_id)
        assert refreshed.password == original_password
        assert Token.query.filter_by(user_id=user_id).count() == 2


def test_update_password_short_new_returns_400(app, client, password_user):
    """
    CHECK a too-short new password is rejected
    data check:
        status: 400
        success: False
    """
    with app.app_context():
        token_hash = Token.query.filter_by(user_id=password_user.user_id).first().token_hash

    response = client.put(
        "/api/v1/auth/password",
        headers=password_headers(token_hash),
        json={"current_password": "OldPass123", "new_password": "abc"},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_update_password_missing_fields_returns_400(app, client, password_user):
    """
    CHECK a body missing either field is rejected
    data check:
        status: 400
    """
    with app.app_context():
        token_hash = Token.query.filter_by(user_id=password_user.user_id).first().token_hash

    response = client.put(
        "/api/v1/auth/password",
        headers=password_headers(token_hash),
        json={"current_password": "OldPass123"},
    )
    assert response.status_code == 400


def test_update_password_requires_auth(client):
    """
    CHECK changing the password without a bearer token returns 401
    data check:
        status: 401
    """
    response = client.put(
        "/api/v1/auth/password",
        json={"current_password": "a", "new_password": "b"},
    )
    assert response.status_code == 401
