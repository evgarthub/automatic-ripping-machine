"""
Unit tests for GET /api/v1/system/drives, POST /system/drives/<name>/eject
and GET /api/v1/system/dashboard
"""
import uuid
from subprocess import CalledProcessError
from unittest.mock import patch

import pytest

from arm.models.job import Job
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


@pytest.fixture()
def sample_drive(app):
    """A seeded drive with real model fields and an associated current job"""
    with app.app_context():
        job = Job("/dev/sr0")
        job.status = "success"
        job.title = "Sample Title"
        job.year = "2015"
        job.video_type = "movie"
        job_uuid = uuid.uuid4().hex
        job.logfile = f"{job_uuid}.log"
        job.stage = job_uuid
        db.session.add(job)
        drive = SystemDrives()
        drive.name = "Sample Drive"
        drive.description = "Sample drive description"
        drive.mount = "/dev/sr0"
        drive.maker = "Sample Maker"
        drive.model = "Sample Model"
        drive.serial = "ABC123"
        drive.connection = "usb"
        drive.firmware = "1.00"
        drive.location = "0:0"
        drive.stale = False
        drive.drive_mode = "auto"
        drive.read_cd = True
        drive.read_dvd = True
        drive.read_bd = False
        drive.job_current = job
        db.session.add(drive)
        db.session.commit()
        yield drive
        db.session.delete(drive)
        db.session.delete(job)
        db.session.commit()


def test_get_drives_returns_real_fields(app, client, auth_headers, sample_drive):
    """
    CHECK drives are serialized with real SystemDrives fields only
    data check:
        status: 200
        success: True
        keys: real model fields, no phantom mount_point/capacity etc.
        type: derived CD/DVD
        processing: True with mirrored current job info
    """
    response = client.get("/api/v1/system/drives", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    data = body["data"]
    assert len(data) == 1
    drive_data = data[0]
    assert set(drive_data.keys()) == {
        "drive_id", "name", "description", "type", "mount", "maker", "model",
        "serial", "connection", "firmware", "location", "stale", "mdisc",
        "drive_mode", "read_cd", "read_dvd", "read_bd", "processing",
        "job_current", "job_previous"
    }
    assert drive_data["drive_id"] == sample_drive.drive_id
    assert drive_data["name"] == "Sample Drive"
    assert drive_data["mount"] == "/dev/sr0"
    assert drive_data["type"] == "CD/DVD"
    assert drive_data["stale"] is False
    assert drive_data["processing"] is True
    assert drive_data["job_current"]["job_id"] == sample_drive.job_id_current
    assert drive_data["job_current"]["title"] == "Sample Title"
    assert drive_data["job_current"]["year"] == "2015"
    assert drive_data["job_current"]["status"] == "success"
    assert drive_data["job_previous"] is None


def test_get_drives_requires_auth(client):
    """
    CHECK getting drives without a bearer token returns 401
    data check:
        status: 401
    """
    response = client.get("/api/v1/system/drives")
    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_eject_unknown_drive_returns_404(client, auth_headers):
    """
    CHECK ejecting a missing drive returns 404
    data check:
        status: 404
        success: False
    """
    response = client.post("/api/v1/system/drives/does-not-exist/eject", headers=auth_headers)
    assert response.status_code == 404
    body = response.get_json()
    assert body["success"] is False
    assert "does-not-exist" in body["error"]


def test_eject_drive_success(app, client, auth_headers):
    """
    CHECK ejecting a drive mirrors the model eject command and reports success
    data check:
        status: 200
        success: True
        message: Drive <name> ejected successfully
    """
    with app.app_context():
        drive = SystemDrives()
        drive.name = "Eject Drive"
        drive.mount = "/dev/sr1"
        db.session.add(drive)
        db.session.commit()
    with patch("arm.models.system_drives.arm_subprocess") as mock_subprocess:
        response = client.post("/api/v1/system/drives/Eject Drive/eject", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["message"] == "Drive Eject Drive ejected successfully"
    mock_subprocess.assert_called_once()
    assert "/dev/sr1" in mock_subprocess.call_args[0][0]


def test_eject_drive_failure(app, client, auth_headers):
    """
    CHECK a failed eject command surfaces an error response
    data check:
        status: 500
        success: False
    """
    with app.app_context():
        drive = SystemDrives()
        drive.name = "Broken Drive"
        drive.mount = "/dev/sr9"
        db.session.add(drive)
        db.session.commit()
    with patch(
        "arm.models.system_drives.arm_subprocess",
        side_effect=CalledProcessError(1, "eject", stderr="eject failed"),
    ):
        response = client.post("/api/v1/system/drives/Broken Drive/eject", headers=auth_headers)
    assert response.status_code == 500
    assert response.get_json()["success"] is False


def test_dashboard_completed_storage_percent(app, client, auth_headers):
    """
    CHECK the dashboard completed storage stats use the completed path values
    data check:
        status: 200
        success: True
        completed percent_used/free_gb: from storage_completed_* values
    """
    with patch("arm.ui.api.v1.system.ServerUtil") as mock_serverutil:
        serverutil = mock_serverutil.return_value
        serverutil.cpu_util = 12.3
        serverutil.cpu_temp = 45.6
        serverutil.memory_free = 7.5
        serverutil.memory_used = 8.5
        serverutil.memory_percent = 53.1
        serverutil.storage_transcode_free = 100.0
        serverutil.storage_transcode_percent = 25.0
        serverutil.storage_completed_free = 200.0
        serverutil.storage_completed_percent = 50.0
        response = client.get("/api/v1/system/dashboard", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    completed = body["data"]["storage"]["completed"]
    assert completed["percent_used"] == 50.0
    assert completed["free_gb"] == 200.0
    assert body["data"]["storage"]["transcode"]["percent_used"] == 25.0
