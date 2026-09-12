"""
Unit tests for GET /api/v1/jobs/<job_id>
"""
import uuid

import pytest

from arm.models.job import Job
from arm.models.track import Track
from arm.ui import db


@pytest.fixture()
def job_with_tracks(app):
    """A finished job with two seeded tracks added out of order"""
    with app.app_context():
        job = Job("/dev/sr0")
        job.status = "success"
        db_job_uuid = uuid.uuid4().hex
        job.logfile = f"{db_job_uuid}.log"
        job.stage = db_job_uuid
        job.label = f"LABEL_{db_job_uuid}"
        db.session.add(job)
        db.session.flush()
        track_two = Track(job.job_id, "02", 3600, "16/9", 25.0, False, "dvd", "basename2", "file2.mkv", 2, 2048)
        track_one = Track(job.job_id, "01", 5400, "16/9", 25.0, True, "dvd", "basename1", "file1.mkv", 12, 4096)
        db.session.add(track_two)
        db.session.add(track_one)
        db.session.commit()
        yield job
        Track.query.filter_by(job_id=job.job_id).delete()
        db.session.delete(job)
        db.session.commit()


def test_job_detail_returns_tracks_ordered(app, client, auth_headers, job_with_tracks):
    """
    CHECK job detail includes the job's tracks ordered by track number
    data check:
        status: 200
        success: True
        tracks: list of 2 serialized tracks ordered "01" then "02"
        track keys/values mirror the Track model
    """
    response = client.get(f"/api/v1/jobs/{job_with_tracks.job_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    data = body["data"]
    assert data["job_id"] == str(job_with_tracks.job_id)
    tracks = data["tracks"]
    assert len(tracks) == 2
    assert [t["track_number"] for t in tracks] == ["01", "02"]
    assert tracks[0]["job_id"] == str(job_with_tracks.job_id)
    assert tracks[0]["length"] == "5400"
    assert tracks[0]["aspect_ratio"] == "16/9"
    assert tracks[0]["fps"] == "25.0"
    assert tracks[0]["main_feature"] == "True"
    assert tracks[0]["basename"] == "basename1"
    assert tracks[0]["filename"] == "file1.mkv"
    assert tracks[0]["chapters"] == "12"
    assert tracks[0]["filesize"] == "4096"
    assert tracks[0]["ripped"] == "False"
    assert tracks[0]["status"] == "None"
    assert tracks[0]["error"] == "None"
    assert tracks[0]["source"] == "dvd"
    assert tracks[0]["process"] == "False"
    assert tracks[1]["filename"] == "file2.mkv"
    assert tracks[1]["main_feature"] == "False"


def test_job_detail_returns_empty_tracks(app, client, auth_headers):
    """
    CHECK job detail returns an empty tracks list when the job has no tracks
    data check:
        status: 200
        success: True
        tracks: []
    """
    with app.app_context():
        job = Job("/dev/sr0")
        job.status = "success"
        db_job_uuid = uuid.uuid4().hex
        job.logfile = f"{db_job_uuid}.log"
        job.stage = db_job_uuid
        job.label = f"LABEL_{db_job_uuid}"
        db.session.add(job)
        db.session.commit()
        job_id = job.job_id
    try:
        response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        body = response.get_json()
        assert body["success"] is True
        assert body["data"]["tracks"] == []
    finally:
        with app.app_context():
            job = Job.query.get(job_id)
            db.session.delete(job)
            db.session.commit()


def test_job_detail_not_found(client, auth_headers):
    """
    CHECK job detail for a missing job returns 404
    data check:
        status: 404
    """
    response = client.get("/api/v1/jobs/999999", headers=auth_headers)
    assert response.status_code == 404


def test_job_detail_requires_auth(client, job_with_tracks):
    """
    CHECK job detail without a bearer token returns 401
    data check:
        status: 401
    """
    response = client.get(f"/api/v1/jobs/{job_with_tracks.job_id}")
    assert response.status_code == 401
    assert response.get_json()["success"] is False
