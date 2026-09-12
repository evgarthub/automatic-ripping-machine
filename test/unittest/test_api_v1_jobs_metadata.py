"""
Unit tests for PUT /api/v1/jobs/<job_id>/metadata
"""
import uuid

import pytest

from arm.models.job import Job
from arm.models.notifications import Notifications
from arm.ui import db


@pytest.fixture()
def sample_job(app):
    """A finished job with existing metadata"""
    with app.app_context():
        job = Job("/dev/sr0")
        job.status = "success"
        job.title = "Old Title"
        job.title_auto = "Old Title"
        job.year = "2001"
        job.year_auto = "2001"
        job.video_type = "movie"
        job.video_type_auto = "movie"
        job.imdb_id = "tt0111111"
        job.imdb_id_auto = "tt0111111"
        job.poster_url = "http://example.com/old.jpg"
        job.poster_url_auto = "http://example.com/old.jpg"
        db_job_uuid = uuid.uuid4().hex
        job.logfile = f"{db_job_uuid}.log"
        job.stage = db_job_uuid
        job.label = f"LABEL_{db_job_uuid}"
        db.session.add(job)
        db.session.commit()
        yield job
        Notifications.query.filter_by(
            title=f"Job: {job.job_id} was updated"
        ).delete(synchronize_session=False)
        db.session.delete(job)
        db.session.commit()


def test_metadata_update_success(app, client, auth_headers, sample_job):
    """
    CHECK updating all metadata fields mirrors the legacy /updatetitle behaviour
    data check:
        status: 200
        success: True
        title/title_manual: cleaned title
        year/year_manual: "2015"
        video_type/video_type_manual: "series"
        imdb_id/imdb_id_manual: "tt2224026"
        poster_url/poster_url_manual: updated url
        hasnicetitle: True
        notification created
    """
    response = client.put(
        f"/api/v1/jobs/{sample_job.job_id}/metadata",
        json={
            "title": "Home: Part II",
            "year": 2015,
            "video_type": "series",
            "imdb_id": "tt2224026",
            "poster_url": "http://example.com/new.jpg",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    data = body["data"]
    assert data["title"] == "Home- Part II"
    assert data["title_manual"] == "Home- Part II"
    assert data["year"] == "2015"
    assert data["year_manual"] == "2015"
    assert data["video_type"] == "series"
    assert data["video_type_manual"] == "series"
    assert data["imdb_id"] == "tt2224026"
    assert data["imdb_id_manual"] == "tt2224026"
    assert data["poster_url"] == "http://example.com/new.jpg"
    assert data["poster_url_manual"] == "http://example.com/new.jpg"

    with app.app_context():
        refreshed = Job.query.get(sample_job.job_id)
        assert refreshed.hasnicetitle is True
        notification = Notifications.query.filter_by(title=f"Job: {sample_job.job_id} was updated").first()
        assert notification is not None
        assert notification.message == (
            "Title: Old Title (2001) was updated to Home: Part II (2015)"
        )


def test_metadata_update_single_field(app, client, auth_headers, sample_job):
    """
    CHECK updating a single field leaves other fields untouched
    data check:
        status: 200
        title: updated
        year: unchanged
    """
    response = client.put(
        f"/api/v1/jobs/{sample_job.job_id}/metadata",
        json={"title": "New Name"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["title"] == "New Name"
    assert data["year"] == "2001"
    assert data["imdb_id"] == "tt0111111"


def test_metadata_update_job_not_found(client, auth_headers):
    """
    CHECK updating metadata for a missing job returns 404
    data check:
        status: 404
    """
    response = client.put("/api/v1/jobs/999999/metadata", json={"title": "Nope"}, headers=auth_headers)
    assert response.status_code == 404


def test_metadata_update_rejects_unknown_fields(client, auth_headers, sample_job):
    """
    CHECK unknown fields are rejected with 400
    data check:
        status: 400
        success: False
        error mentions the unknown field
    """
    response = client.put(
        f"/api/v1/jobs/{sample_job.job_id}/metadata",
        json={"title": "Valid", "bogus_field": "nope"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert "bogus_field" in body["error"]


def test_metadata_update_requires_at_least_one_field(client, auth_headers, sample_job):
    """
    CHECK an empty object is rejected with 400
    data check:
        status: 400
    """
    response = client.put(f"/api/v1/jobs/{sample_job.job_id}/metadata", json={}, headers=auth_headers)
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_metadata_update_rejects_invalid_year(client, auth_headers, sample_job):
    """
    CHECK year must be an int or digit string of max 4 characters
    data check:
        status: 400 for bool, non-numeric and overlong values
    """
    for bad_year in (True, "abcd", "20155", None, 20.5):
        response = client.put(
            f"/api/v1/jobs/{sample_job.job_id}/metadata",
            json={"year": bad_year},
            headers=auth_headers,
        )
        assert response.status_code == 400, f"year={bad_year!r} should be rejected"
        assert response.get_json()["success"] is False


def test_metadata_update_rejects_invalid_strings(client, auth_headers, sample_job):
    """
    CHECK string fields must be non-empty strings
    data check:
        status: 400 for empty string, wrong type and whitespace only values
    """
    for field in ("title", "video_type", "imdb_id", "poster_url"):
        for bad_value in ("", 42, None, "   "):
            response = client.put(
                f"/api/v1/jobs/{sample_job.job_id}/metadata",
                json={field: bad_value},
                headers=auth_headers,
            )
            assert response.status_code == 400, f"{field}={bad_value!r} should be rejected"
            assert response.get_json()["success"] is False


def test_metadata_update_requires_json_body(client, auth_headers, sample_job):
    """
    CHECK a missing or non-json body is rejected with 400
    data check:
        status: 400
    """
    response = client.put(f"/api/v1/jobs/{sample_job.job_id}/metadata", headers=auth_headers)
    assert response.status_code == 400
    response = client.put(
        f"/api/v1/jobs/{sample_job.job_id}/metadata",
        data="not json",
        headers=auth_headers,
        content_type="application/json",
    )
    assert response.status_code == 400


def test_metadata_update_requires_auth(client, sample_job):
    """
    CHECK updating metadata without a bearer token returns 401
    data check:
        status: 401
    """
    response = client.put(f"/api/v1/jobs/{sample_job.job_id}/metadata", json={"title": "No Auth"})
    assert response.status_code == 401
    assert response.get_json()["success"] is False
