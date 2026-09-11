"""
Unit tests for POST /api/v1/system/drives/scan, PUT/DELETE /api/v1/system/drives/<id>
and POST /api/v1/system/drives/<id>/manual
"""
from subprocess import CalledProcessError
from unittest.mock import MagicMock, patch

import pytest

from arm.models.system_drives import SystemDrives
from arm.ui import db


@pytest.fixture(autouse=True)
def clean_drives(app):
    """Remove all drives before and after each test for isolation"""
    with app.app_context():
        SystemDrives.query.delete()
        db.session.commit()
        yield
        SystemDrives.query.delete()
        db.session.commit()


def make_drive(name="Admin Drive", mount="/dev/sr0"):
    """Create and commit a drive row, returning it"""
    drive = SystemDrives()
    drive.name = name
    drive.description = "original description"
    drive.mount = mount
    drive.drive_mode = "auto"
    db.session.add(drive)
    db.session.commit()
    return drive


def test_scan_drives_reports_new_count(app, client, auth_headers):
    """
    CHECK scanning calls drives_update and returns its new drive count
    data check:
        status: 200
        success: True
        new_drives: 2
    """
    with patch("arm.ui.settings.DriveUtils.drives_update", return_value=2) as mock_update:
        response = client.post("/api/v1/system/drives/scan", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["new_drives"] == 2
    mock_update.assert_called_once_with()


def test_scan_drives_requires_auth(client):
    """
    CHECK scanning without a bearer token returns 401
    data check:
        status: 401
    """
    response = client.post("/api/v1/system/drives/scan")
    assert response.status_code == 401


def test_update_drive_success(app, client, auth_headers):
    """
    CHECK PUT updates name/description/drive_mode like the legacy systeminfo form
    data check:
        status: 200
        success: True
        data: full drive serialization with the new values
    """
    with app.app_context():
        drive = make_drive()
        drive_id = drive.drive_id

    response = client.put(
        f"/api/v1/system/drives/{drive_id}",
        headers=auth_headers,
        json={"name": "Renamed", "description": "new description", "drive_mode": "manual"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    drive_data = body["data"]
    assert drive_data["drive_id"] == drive_id
    assert drive_data["name"] == "Renamed"
    assert drive_data["description"] == "new description"
    assert drive_data["drive_mode"] == "manual"

    with app.app_context():
        refreshed = SystemDrives.query.get(drive_id)
        assert refreshed.name == "Renamed"
        assert refreshed.drive_mode == "manual"


def test_update_drive_invalid_mode_returns_400(app, client, auth_headers):
    """
    CHECK PUT rejects a drive_mode outside the model's valid auto/manual set
    data check:
        status: 400
        success: False
    """
    with app.app_context():
        drive = make_drive()
        drive_id = drive.drive_id

    response = client.put(
        f"/api/v1/system/drives/{drive_id}",
        headers=auth_headers,
        json={"drive_mode": "hyperspace"},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_update_drive_unknown_returns_404(client, auth_headers):
    """
    CHECK PUT on a missing drive id returns 404
    data check:
        status: 404
    """
    response = client.put(
        "/api/v1/system/drives/999999",
        headers=auth_headers,
        json={"name": "Ghost"},
    )
    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_delete_drive_success(app, client, auth_headers):
    """
    CHECK DELETE removes the SystemDrives row like the legacy drive_remove
    data check:
        status: 200
        success: True
        message: contains the drive mount
        drive no longer in database
    """
    with app.app_context():
        drive = make_drive(mount="/dev/sr5")
        drive_id = drive.drive_id

    response = client.delete(f"/api/v1/system/drives/{drive_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert "/dev/sr5" in body["message"]

    with app.app_context():
        assert SystemDrives.query.get(drive_id) is None


def test_delete_drive_unknown_returns_404(client, auth_headers):
    """
    CHECK DELETE on a missing drive id returns 404
    data check:
        status: 404
    """
    response = client.delete("/api/v1/system/drives/999999", headers=auth_headers)
    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_manual_start_success(app, client, auth_headers):
    """
    CHECK manual start spawns the docker wrapper script and reports the legacy message
    data check:
        status: 200
        success: True
        message: Manually starting a job on Drive: '<name>'
        Popen called with wrapper path and stripped dev path
    """
    with app.app_context():
        drive = make_drive(name="Manual Drive", mount="/dev/sr3")
        drive_id = drive.drive_id

    process = MagicMock()
    process.communicate.return_value = ("started", "")
    process.returncode = 0
    with patch("arm.ui.api.v1.system.subprocess.Popen", return_value=process) as mock_popen:
        response = client.post(f"/api/v1/system/drives/{drive_id}/manual", headers=auth_headers)

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["message"] == "Manually starting a job on Drive: 'Manual Drive'"
    cmd = mock_popen.call_args[0][0]
    assert "scripts/docker/docker_arm_wrapper.sh sr3" in cmd
    process.communicate.assert_called_once()


def test_manual_start_failure(app, client, auth_headers):
    """
    CHECK a non-zero returncode from the wrapper surfaces the legacy failure message
    data check:
        status: 500
        success: False
        error: Failed to start a job on Drive: '<name>' See logs for info
    """
    with app.app_context():
        drive = make_drive(name="Broken Drive", mount="/dev/sr4")
        drive_id = drive.drive_id

    process = MagicMock()
    process.communicate.return_value = ("", "boom")
    process.returncode = 1
    with patch("arm.ui.api.v1.system.subprocess.Popen", return_value=process):
        response = client.post(f"/api/v1/system/drives/{drive_id}/manual", headers=auth_headers)

    assert response.status_code == 500
    body = response.get_json()
    assert body["success"] is False
    assert body["error"] == "Failed to start a job on Drive: 'Broken Drive' See logs for info"


def test_manual_start_popen_exception(app, client, auth_headers):
    """
    CHECK Popen raising CalledProcessError is reported as a failure, not a crash
    data check:
        status: 500
        success: False
    """
    with app.app_context():
        drive = make_drive(name="Exploding Drive", mount="/dev/sr6")
        drive_id = drive.drive_id

    with patch(
        "arm.ui.api.v1.system.subprocess.Popen",
        side_effect=CalledProcessError(1, "wrapper"),
    ):
        response = client.post(f"/api/v1/system/drives/{drive_id}/manual", headers=auth_headers)

    assert response.status_code == 500
    assert response.get_json()["success"] is False


def test_manual_start_unknown_returns_404(client, auth_headers):
    """
    CHECK manual start on a missing drive id returns 404
    data check:
        status: 404
    """
    response = client.post("/api/v1/system/drives/999999/manual", headers=auth_headers)
    assert response.status_code == 404
    assert response.get_json()["success"] is False
