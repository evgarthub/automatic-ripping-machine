"""
Unit tests for the /api/v1/settings suite
The autouse fixture rewrites the isolated temp arm.yaml so abcde/apprise
writes hit temp files instead of the repo copies, then restores the
original conftest config after each test
"""
import importlib
import os
from unittest.mock import MagicMock

import pytest

import arm.config.config as cfg
import arm.ripper.utils as ripper_utils
from arm.models.ui_settings import UISettings
from arm.ui import db

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO_ROOT_POSIX = REPO_ROOT.replace("\\", "/")
CONFIG_PATH = os.environ["ARM_CONFIG_FILE"]
TEST_DIR_POSIX = os.path.dirname(CONFIG_PATH).replace("\\", "/")
ORIGINAL_ABCDE_PATH = (REPO_ROOT + "/setup/.abcde.conf").replace("\\", "/")


def write_arm_config(abcde_path, apprise_path):
    """Write the isolated temp arm.yaml and hot-reload the config module"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as config_file:
        config_file.write(f"INSTALLPATH: {REPO_ROOT_POSIX}/\n")
        config_file.write(f"DBFILE: {TEST_DIR_POSIX}/arm.db\n")
        config_file.write(f"LOGPATH: {TEST_DIR_POSIX}/logs/\n")
        config_file.write("LOGLEVEL: ERROR\n")
        config_file.write(f"ABCDE_CONFIG_FILE: {abcde_path}\n")
        config_file.write(f"APPRISE: {apprise_path}\n")
        config_file.write("DISABLE_LOGIN: false\n")
    importlib.reload(cfg)


@pytest.fixture(autouse=True)
def isolated_config_files():
    """Point abcde/apprise config paths at temp files for every test"""
    abcde_path = os.path.join(TEST_DIR_POSIX, "abcde.conf")
    apprise_path = os.path.join(TEST_DIR_POSIX, "apprise.yaml")
    with open(abcde_path, "w", encoding="utf-8") as abcde_file:
        abcde_file.write("# test abcde config\n")
    with open(apprise_path, "w", encoding="utf-8") as apprise_file:
        apprise_file.write("urls:\n  - json://localhost\n")
    write_arm_config(abcde_path.replace("\\", "/"), apprise_path.replace("\\", "/"))
    yield {"abcde": abcde_path.replace("\\", "/"), "apprise": apprise_path.replace("\\", "/")}
    write_arm_config(ORIGINAL_ABCDE_PATH, "")


@pytest.fixture()
def ui_settings(app):
    """A UISettings row at id=1 like ARM setup creates"""
    with app.app_context():
        UISettings.query.delete()
        db.session.commit()
        row = UISettings(use_icons=True, save_remote_images=True, bootstrap_skin="bootstrap",
                         language="en", index_refresh=2000, database_limit=50, notify_refresh=10)
        db.session.add(row)
        db.session.commit()
        yield row


def test_get_settings(client, auth_headers):
    """
    CHECK GET returns all arm.yaml values, the comments map and read_only flag
    data check:
        status: 200
        values contains template + test config keys with parsed types
        comments contains the arm.yaml comments
        read_only: False
    """
    response = client.get("/api/v1/settings", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["values"]["DISABLE_LOGIN"] is False
    assert body["data"]["values"]["LOGLEVEL"] == "ERROR"
    assert "PREVENT_99" in body["data"]["values"]
    assert "Log level" in body["data"]["comments"]["LOGLEVEL"]
    assert body["data"]["read_only"] is False


def test_get_settings_requires_auth(client):
    """
    CHECK GET without a bearer token returns 401
    data check:
        status: 401
    """
    response = client.get("/api/v1/settings")
    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_update_settings_success(client, auth_headers):
    """
    CHECK PUT updates a bool and a str key, rebuilds the temp arm.yaml and
    hot-reloads the config module like the legacy save_settings
    data check:
        status: 200
        PREVENT_99: False (string "false" coerced)
        ARM_NAME: "api-test-arm"
        temp arm.yaml contains the new yaml lines
        cfg module reloaded from the isolated temp path
    """
    response = client.put(
        "/api/v1/settings",
        json={"PREVENT_99": "false", "ARM_NAME": "api-test-arm"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["values"]["PREVENT_99"] is False
    assert body["data"]["values"]["ARM_NAME"] == "api-test-arm"

    with open(CONFIG_PATH, encoding="utf-8") as config_file:
        yaml_content = config_file.read()
    assert "PREVENT_99: false" in yaml_content
    assert 'ARM_NAME: "api-test-arm"' in yaml_content

    assert cfg.arm_config_path == CONFIG_PATH
    assert cfg.arm_config["PREVENT_99"] is False
    assert cfg.arm_config["ARM_NAME"] == "api-test-arm"

    get_response = client.get("/api/v1/settings", headers=auth_headers)
    assert get_response.status_code == 200
    get_values = get_response.get_json()["data"]["values"]
    assert get_values["PREVENT_99"] is False
    assert get_values["ARM_NAME"] == "api-test-arm"


def test_update_settings_requires_auth(client):
    """
    CHECK PUT without a bearer token returns 401
    data check:
        status: 401
    """
    response = client.put("/api/v1/settings", json={"ARM_NAME": "nope"})
    assert response.status_code == 401


def test_update_settings_empty_body(client, auth_headers):
    """
    CHECK PUT with no JSON body returns 400
    data check:
        status: 400
    """
    response = client.put("/api/v1/settings", headers=auth_headers)
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_update_settings_unknown_key(client, auth_headers):
    """
    CHECK PUT with keys not in arm.yaml returns 400 listing them
    data check:
        status: 400
        error mentions NOT_A_REAL_KEY
    """
    response = client.put(
        "/api/v1/settings",
        json={"NOT_A_REAL_KEY": "value"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "NOT_A_REAL_KEY" in response.get_json()["error"]


def test_update_settings_wrong_type(client, auth_headers):
    """
    CHECK PUT values that cannot be coerced to the current type return 400
    data check:
        status: 400 for str-into-int, non-bool-string-into-bool and bool-into-int
    """
    response = client.put(
        "/api/v1/settings",
        json={"MANUAL_WAIT_TIME": "banana"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "MANUAL_WAIT_TIME" in response.get_json()["error"]

    response = client.put(
        "/api/v1/settings",
        json={"PREVENT_99": "yes"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "PREVENT_99" in response.get_json()["error"]

    response = client.put(
        "/api/v1/settings",
        json={"MANUAL_WAIT_TIME": True},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_update_settings_read_only(client, auth_headers):
    """
    CHECK PUT against a read-only arm.yaml returns 409 and leaves the file
    unchanged; the file is marked read-only via chmod and restored after
    data check:
        status: 409
        error mentions read-only
        temp arm.yaml unchanged
    """
    with open(CONFIG_PATH, encoding="utf-8") as config_file:
        original = config_file.read()
    os.chmod(CONFIG_PATH, 0o444)
    try:
        response = client.put(
            "/api/v1/settings",
            json={"ARM_NAME": "nope"},
            headers=auth_headers,
        )
        assert response.status_code == 409
        assert "read-only" in response.get_json()["error"]
        with open(CONFIG_PATH, encoding="utf-8") as config_file:
            assert config_file.read() == original
    finally:
        os.chmod(CONFIG_PATH, 0o666)


def test_get_ui_settings(app, client, auth_headers, ui_settings):
    """
    CHECK GET returns the UISettings row (id=1) as a dict of strings
    data check:
        status: 200
        use_icons: "True"
        index_refresh: "2000"
        language: "en"
    """
    response = client.get("/api/v1/settings/ui", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["id"] == "1"
    assert body["data"]["use_icons"] == "True"
    assert body["data"]["index_refresh"] == "2000"
    assert body["data"]["language"] == "en"


def test_get_ui_settings_not_found(app, client, auth_headers):
    """
    CHECK GET returns 404 with a clear error when the row is missing
    data check:
        status: 404
    """
    with app.app_context():
        UISettings.query.delete()
        db.session.commit()
    response = client.get("/api/v1/settings/ui", headers=auth_headers)
    assert response.status_code == 404
    assert "UI settings not found" in response.get_json()["error"]


def test_update_ui_settings(app, client, auth_headers, ui_settings):
    """
    CHECK PUT saves the editable fields, accepting bool strings like the
    legacy save_ui_settings (.strip().lower() == "true")
    data check:
        status: 200
        use_icons: False (from string "false")
        save_remote_images: True (json bool)
        index_refresh: 5000 (string coerced)
    """
    response = client.put(
        "/api/v1/settings/ui",
        json={
            "use_icons": "false",
            "save_remote_images": True,
            "index_refresh": "5000",
            "database_limit": 100,
            "notify_refresh": 5,
            "bootstrap_skin": "cerulean",
            "language": "de",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.get_json()["success"] is True

    with app.app_context():
        row = UISettings.query.get(1)
        assert row.use_icons is False
        assert row.save_remote_images is True
        assert row.index_refresh == 5000
        assert row.database_limit == 100
        assert row.notify_refresh == 5
        assert row.bootstrap_skin == "cerulean"
        assert row.language == "de"


def test_update_ui_settings_unknown_field(client, auth_headers, ui_settings):
    """
    CHECK PUT with a field outside the editable set returns 400
    data check:
        status: 400
    """
    response = client.put(
        "/api/v1/settings/ui",
        json={"not_a_field": 1},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "not_a_field" in response.get_json()["error"]


def test_update_ui_settings_invalid_int(client, auth_headers, ui_settings):
    """
    CHECK PUT with a non-integer refresh value returns 400
    data check:
        status: 400
    """
    response = client.put(
        "/api/v1/settings/ui",
        json={"index_refresh": "soon"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "index_refresh" in response.get_json()["error"]


def test_get_abcde_settings(client, auth_headers, isolated_config_files):
    """
    CHECK GET returns the temp abcde.conf content and read_only flag
    data check:
        status: 200
        content matches the temp file
        read_only: False
    """
    response = client.get("/api/v1/settings/abcde", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["content"] == "# test abcde config\n"
    assert body["data"]["read_only"] is False


def test_update_abcde_settings(client, auth_headers, isolated_config_files):
    """
    CHECK PUT writes the content with Windows line endings cleaned to \n,
    mirroring the legacy save_abcde cleanup
    data check:
        status: 200
        temp abcde.conf contains no \r
        cfg.abcde_config updated in memory
    """
    response = client.put(
        "/api/v1/settings/abcde",
        json={"content": "# line one\r\n# line two\r\n"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["content"] == "# line one\n# line two"

    with open(isolated_config_files["abcde"], encoding="utf-8") as abcde_file:
        written = abcde_file.read()
    assert "\r" not in written
    assert written == "# line one\n# line two"
    assert cfg.abcde_config == "# line one\n# line two"


def test_update_abcde_settings_missing_content(client, auth_headers):
    """
    CHECK PUT without a string content field returns 400
    data check:
        status: 400
    """
    response = client.put("/api/v1/settings/abcde", json={}, headers=auth_headers)
    assert response.status_code == 400


def test_update_abcde_settings_read_only(client, auth_headers, isolated_config_files):
    """
    CHECK PUT against a read-only abcde.conf returns 409
    data check:
        status: 409
    """
    abcde_path = isolated_config_files["abcde"]
    os.chmod(abcde_path, 0o444)
    try:
        response = client.put(
            "/api/v1/settings/abcde",
            json={"content": "# nope"},
            headers=auth_headers,
        )
        assert response.status_code == 409
        assert "read-only" in response.get_json()["error"]
    finally:
        os.chmod(abcde_path, 0o666)


def test_get_apprise_settings(client, auth_headers, isolated_config_files):
    """
    CHECK GET returns the temp apprise.yaml content and read_only flag
    data check:
        status: 200
        content matches the temp file
        read_only: False
    """
    response = client.get("/api/v1/settings/apprise", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["content"] == "urls:\n  - json://localhost\n"
    assert body["data"]["read_only"] is False


def test_update_apprise_settings(client, auth_headers, isolated_config_files):
    """
    CHECK PUT writes valid YAML to the temp apprise.yaml and hot-reloads the
    config module so cfg.apprise_config reflects the new content
    data check:
        status: 200
        temp apprise.yaml updated
        cfg.apprise_config parsed from the new content
    """
    response = client.put(
        "/api/v1/settings/apprise",
        json={"content": "urls:\n  - pbul://abc123\n"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["content"] == "urls:\n  - pbul://abc123\n"

    with open(isolated_config_files["apprise"], encoding="utf-8") as apprise_file:
        assert apprise_file.read() == "urls:\n  - pbul://abc123\n"
    assert cfg.apprise_config_path == isolated_config_files["apprise"]
    assert cfg.apprise_config == {"urls": ["pbul://abc123"]}


def test_update_apprise_settings_invalid_yaml(client, auth_headers):
    """
    CHECK PUT with unparseable YAML returns 400 with the parse error
    data check:
        status: 400
        error mentions Invalid YAML
    """
    response = client.put(
        "/api/v1/settings/apprise",
        json={"content": "urls: [unclosed"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Invalid YAML" in response.get_json()["error"]


def test_update_apprise_settings_non_mapping(client, auth_headers):
    """
    CHECK PUT with YAML that does not parse to a mapping returns 400
    data check:
        status: 400
    """
    response = client.put(
        "/api/v1/settings/apprise",
        json={"content": "just a string"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "mapping" in response.get_json()["error"]


def test_update_apprise_settings_read_only(client, auth_headers, isolated_config_files):
    """
    CHECK PUT against a read-only apprise.yaml returns 409
    data check:
        status: 409
    """
    apprise_path = isolated_config_files["apprise"]
    os.chmod(apprise_path, 0o444)
    try:
        response = client.put(
            "/api/v1/settings/apprise",
            json={"content": "urls: []\n"},
            headers=auth_headers,
        )
        assert response.status_code == 409
        assert "read-only" in response.get_json()["error"]
    finally:
        os.chmod(apprise_path, 0o666)


def test_apprise_test_notification(client, auth_headers, monkeypatch):
    """
    CHECK POST sends the legacy testapprise message through ripper notify
    with the ARM notification title and no job
    data check:
        status: 200
        message matches the legacy text
        notify called once with (None, "ARM notification", message)
    """
    notify_mock = MagicMock()
    monkeypatch.setattr(ripper_utils, "notify", notify_mock)
    response = client.post("/api/v1/settings/apprise/test", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    expected_message = "This is a notification by the ARM-Notification Test!"
    assert body["data"]["message"] == expected_message
    notify_mock.assert_called_once_with(None, "ARM notification", expected_message)


def test_apprise_test_notification_with_server_url(client, auth_headers, monkeypatch):
    """
    CHECK POST appends the server URL when UI_BASE_URL and WEBSERVER_PORT
    are set, mirroring the legacy testapprise
    data check:
        status: 200
        message ends with the server URL
    """
    notify_mock = MagicMock()
    monkeypatch.setattr(ripper_utils, "notify", notify_mock)
    with open(CONFIG_PATH, "a", encoding="utf-8") as config_file:
        config_file.write('UI_BASE_URL: "192.168.0.10"\n')
    importlib.reload(cfg)

    response = client.post("/api/v1/settings/apprise/test", headers=auth_headers)
    assert response.status_code == 200
    expected_message = ("This is a notification by the ARM-Notification Test!"
                        " Server URL: http://192.168.0.10:8080")
    assert response.get_json()["data"]["message"] == expected_message
    notify_mock.assert_called_once_with(None, "ARM notification", expected_message)
