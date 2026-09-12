"""
Shared fixtures for API v1 unit tests
Sets up an isolated ARM config, database and Flask test client
Linux-only modules (pyudev, discid) are stubbed so the suite runs on any OS
"""
import os
import sys
import tempfile
import uuid
from unittest.mock import MagicMock

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

pyudev_stub = MagicMock()
pyudev_stub.Devices.from_device_file.return_value.items.return_value = []
sys.modules["pyudev"] = pyudev_stub

for _module_name in ("fcntl", "discid", "netifaces"):
    try:
        __import__(_module_name)
    except Exception:
        sys.modules[_module_name] = MagicMock()

TEST_DIR = tempfile.mkdtemp(prefix="arm_api_tests_")
TEST_DIR_POSIX = TEST_DIR.replace("\\", "/")
TEST_CONFIG = {
    "INSTALLPATH": REPO_ROOT.replace("\\", "/") + "/",
    "DBFILE": f"{TEST_DIR_POSIX}/arm.db",
    "LOGPATH": f"{TEST_DIR_POSIX}/logs/",
    "LOGLEVEL": "ERROR",
    "ABCDE_CONFIG_FILE": (REPO_ROOT + "/setup/.abcde.conf").replace("\\", "/"),
    "APPRISE": "",
    "DISABLE_LOGIN": False,
}
_config_path = os.path.join(TEST_DIR, "arm.yaml")
with open(_config_path, "w", encoding="utf-8") as _config_file:
    for _key, _value in TEST_CONFIG.items():
        _config_file.write(f"{_key}: {_value}\n")
os.environ["ARM_CONFIG_FILE"] = _config_path

from arm.ui import app as flask_app, db  # noqa: E402
from arm.models.user import User  # noqa: E402
from arm.models.token import Token  # noqa: E402


@pytest.fixture(scope="session")
def app():
    """Flask app with tables created once for the whole test session"""
    with flask_app.app_context():
        db.create_all()
        yield flask_app


@pytest.fixture()
def client(app):
    """Flask test client"""
    return app.test_client()


@pytest.fixture()
def auth_headers(app):
    """Valid bearer token authorization headers"""
    with app.app_context():
        suffix = uuid.uuid4().hex
        user = User(email=f"api_test_{suffix}@example.com", password="password", hashed="hash")
        db.session.add(user)
        db.session.commit()
        token = Token(user_id=user.user_id, token_hash=f"test-token-{suffix}", expiry_hours=24)
        db.session.add(token)
        db.session.commit()
        yield {"Authorization": f"Bearer {token.token_hash}"}
        db.session.delete(token)
        db.session.delete(user)
        db.session.commit()
