"""
Unit tests for GET/POST /api/v1/jobs/<job_id>/titlesearch and the details lookup
"""
import uuid

import pytest

from arm.models.job import Job
from arm.models.notifications import Notifications
from arm.ui import db


def patch_metadata_selector(monkeypatch, responses):
    """Patch metadata_selector where the routes look it up and record every call

    responses are returned in order, the last one is reused for extra calls
    """
    calls = []

    def fake(func, query="", year="", imdb_id=""):
        calls.append((func, query, year, imdb_id))
        return responses[min(len(calls) - 1, len(responses) - 1)]

    monkeypatch.setattr("arm.ui.api.v1.jobs.metadata_selector", fake)
    return calls


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
        db.session.delete(job)
        db.session.commit()


@pytest.fixture()
def cleanup_notifications(app, sample_job):
    """Delete notifications created for the sample job during a test"""
    yield
    with app.app_context():
        Notifications.query.filter_by(
            title=f"Job: {sample_job.job_id} was updated"
        ).delete(synchronize_session=False)
        db.session.commit()


def test_title_search_success(app, client, auth_headers, sample_job, monkeypatch):
    """
    CHECK the search endpoint normalizes provider results
    data check:
        status: 200
        success: True
        game hits and hits without an imdb id are dropped
        results have only imdb_id/title/year/poster/type keys
        retried_without_year: False
        metadata_selector called once with ("search", title, year)
    """
    calls = patch_metadata_selector(monkeypatch, [{
        "Search": [
            {"Title": "Matrix Game", "Year": "2003", "imdbID": "tt0330300",
             "Type": "game", "Poster": "http://x/game.jpg"},
            {"Title": "No Imdb Entry", "Year": "1999", "Type": "movie",
             "Poster": "http://x/none.jpg"},
            {"Title": "The Matrix", "Year": "1999", "imdbID": "tt0133093",
             "Type": "movie", "Poster": "http://x/matrix.jpg"},
            {"Title": "The Matrix Show", "Year": "2021", "imdbID": "tt1234567",
             "Type": "series", "Poster": "http://x/show.jpg"},
        ]
    }])
    response = client.get(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
        query_string={"title": "The Matrix", "year": "1999"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    data = body["data"]
    assert data["retried_without_year"] is False
    results = data["results"]
    assert len(results) == 2
    assert results[0] == {
        "imdb_id": "tt0133093",
        "title": "The Matrix",
        "year": "1999",
        "poster": "http://x/matrix.jpg",
        "type": "movie",
    }
    assert results[1]["imdb_id"] == "tt1234567"
    assert results[1]["type"] == "series"
    for result in results:
        assert set(result.keys()) == {"imdb_id", "title", "year", "poster", "type"}
    assert calls == [("search", "The Matrix", "1999", "")]


def test_title_search_retries_without_year(client, auth_headers, sample_job, monkeypatch):
    """
    CHECK an empty search with a year is retried without the year
    data check:
        status: 200
        retried_without_year: True
        second call had an empty year
    """
    calls = patch_metadata_selector(monkeypatch, [
        {"Search": []},
        {"Search": [
            {"Title": "The Matrix", "Year": "1999", "imdbID": "tt0133093",
             "Type": "movie", "Poster": "http://x/matrix.jpg"},
        ]},
    ])
    response = client.get(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
        query_string={"title": "The Matrix", "year": "1999"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["retried_without_year"] is True
    assert len(body["data"]["results"]) == 1
    assert body["data"]["results"][0]["imdb_id"] == "tt0133093"
    assert len(calls) == 2
    assert calls[0] == ("search", "The Matrix", "1999", "")
    assert calls[1] == ("search", "The Matrix", "", "")


def test_title_search_no_results(client, auth_headers, sample_job, monkeypatch):
    """
    CHECK an empty search with and without a year is reported
    data check:
        status: 200
        results: []
        retried_without_year: True when a year was given, False otherwise
    """
    calls = patch_metadata_selector(monkeypatch, [{"Search": []}, {"Search": []}])
    response = client.get(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
        query_string={"title": "Unknown Movie", "year": "1899"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["results"] == []
    assert body["data"]["retried_without_year"] is True
    assert len(calls) == 2

    calls = patch_metadata_selector(monkeypatch, [{"Search": []}])
    response = client.get(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
        query_string={"title": "Unknown Movie"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["data"]["results"] == []
    assert body["data"]["retried_without_year"] is False
    assert calls == [("search", "Unknown Movie", "", "")]


def test_title_search_requires_title(client, auth_headers, sample_job):
    """
    CHECK a missing or blank title is rejected with 400
    data check:
        status: 400
        success: False
    """
    response = client.get(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
        query_string={"year": "1999"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"] == "Title parameter is required"

    response = client.get(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
        query_string={"title": "   "},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_title_search_job_not_found(client, auth_headers):
    """
    CHECK searching for a missing job returns 404
    data check:
        status: 404
    """
    response = client.get(
        "/api/v1/jobs/999999/titlesearch",
        query_string={"title": "The Matrix"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_title_search_requires_auth(client, sample_job):
    """
    CHECK searching without a bearer token returns 401
    data check:
        status: 401
        success: False
    """
    response = client.get(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
        query_string={"title": "The Matrix"},
    )
    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_title_search_details_success(client, auth_headers, sample_job, monkeypatch):
    """
    CHECK the details endpoint normalizes the provider response
    data check:
        status: 200
        success: True
        keys: imdb_id/title/year/poster/type/plot/background_url
        metadata_selector called once with ("get_details", "", "", imdb_id)
    """
    calls = patch_metadata_selector(monkeypatch, [{
        "Title": "The Matrix",
        "Year": "1999",
        "imdbID": "tt0133093",
        "Poster": "http://x/matrix.jpg",
        "Type": "movie",
        "Plot": "A computer hacker learns the truth.",
        "background_url": "http://x/background.jpg",
    }])
    response = client.get(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch/details",
        query_string={"imdb_id": "tt0133093"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"] == {
        "imdb_id": "tt0133093",
        "title": "The Matrix",
        "year": "1999",
        "poster": "http://x/matrix.jpg",
        "type": "movie",
        "plot": "A computer hacker learns the truth.",
        "background_url": "http://x/background.jpg",
    }
    assert calls == [("get_details", "", "", "tt0133093")]


def test_title_search_details_not_found(client, auth_headers, sample_job, monkeypatch):
    """
    CHECK a failed details lookup returns 404
    data check:
        status: 404
        success: False
        error: No details found
    """
    patch_metadata_selector(monkeypatch, [None])
    response = client.get(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch/details",
        query_string={"imdb_id": "tt0000000"},
        headers=auth_headers,
    )
    assert response.status_code == 404
    body = response.get_json()
    assert body["success"] is False
    assert body["error"] == "No details found"


def test_title_search_details_requires_imdb_id(client, auth_headers, sample_job):
    """
    CHECK a missing imdb_id parameter is rejected with 400
    data check:
        status: 400
        success: False
    """
    response = client.get(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch/details",
        headers=auth_headers,
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"] == "imdb_id parameter is required"


def test_title_search_details_requires_auth(client, sample_job):
    """
    CHECK the details endpoint without a bearer token returns 401
    data check:
        status: 401
        success: False
    """
    response = client.get(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch/details",
        query_string={"imdb_id": "tt0133093"},
    )
    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_title_search_apply_by_imdb_id(app, client, auth_headers, sample_job,
                                       monkeypatch, cleanup_notifications):
    """
    CHECK applying details by imdb_id updates the job like the legacy updatetitle
    data check:
        status: 200
        title/title_manual: cleaned title
        year/video_type/imdb_id/poster_url updated with their *_manual columns
        hasnicetitle: True
        notification created with the legacy message format
        response data is the updated job dict
    """
    patch_metadata_selector(monkeypatch, [{
        "Title": "Home: Part II",
        "Year": "1990",
        "imdbID": "tt0120737",
        "Poster": "http://x/new.jpg",
        "Type": "movie",
        "Plot": "plot",
        "background_url": "http://x/bg.jpg",
    }])
    response = client.post(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
        json={"imdb_id": "tt0120737"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    data = body["data"]
    assert data["title"] == "Home- Part II"
    assert data["year"] == "1990"
    assert data["imdb_id"] == "tt0120737"

    with app.app_context():
        refreshed = Job.query.get(sample_job.job_id)
        assert refreshed.title == "Home- Part II"
        assert refreshed.title_manual == "Home- Part II"
        assert refreshed.year == "1990"
        assert refreshed.year_manual == "1990"
        assert refreshed.video_type == "movie"
        assert refreshed.video_type_manual == "movie"
        assert refreshed.imdb_id == "tt0120737"
        assert refreshed.imdb_id_manual == "tt0120737"
        assert refreshed.poster_url == "http://x/new.jpg"
        assert refreshed.poster_url_manual == "http://x/new.jpg"
        assert refreshed.hasnicetitle is True
        notification = Notifications.query.filter_by(
            title=f"Job: {sample_job.job_id} was updated"
        ).first()
        assert notification is not None
        assert notification.message == (
            "Title: Old Title (2001) was updated to Home: Part II (1990)"
        )


def test_title_search_apply_custom_title(app, client, auth_headers, sample_job,
                                         cleanup_notifications):
    """
    CHECK applying a custom title only touches the title and year fields
    data check:
        status: 200
        title/title_manual and year/year_manual updated
        video_type/imdb_id/poster_url untouched
        hasnicetitle: True
        notification created
    """
    response = client.post(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
        json={"title": "My Custom Title", "year": "1999"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    data = body["data"]
    assert data["title"] == "My Custom Title"
    assert data["year"] == "1999"

    with app.app_context():
        refreshed = Job.query.get(sample_job.job_id)
        assert refreshed.title == "My Custom Title"
        assert refreshed.title_manual == "My Custom Title"
        assert refreshed.year == "1999"
        assert refreshed.year_manual == "1999"
        assert refreshed.video_type == "movie"
        assert refreshed.imdb_id == "tt0111111"
        assert refreshed.poster_url == "http://example.com/old.jpg"
        assert refreshed.hasnicetitle is True
        notification = Notifications.query.filter_by(
            title=f"Job: {sample_job.job_id} was updated"
        ).first()
        assert notification is not None
        assert notification.message == (
            "Title: Old Title (2001) was updated to My Custom Title (1999)"
        )


def test_title_search_apply_rejects_imdb_and_title(client, auth_headers, sample_job,
                                                   monkeypatch):
    """
    CHECK imdb_id combined with title/year is rejected with 400
    data check:
        status: 400
        success: False
        metadata_selector not called
    """
    calls = patch_metadata_selector(monkeypatch, [{"Title": "Nope"}])
    response = client.post(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
        json={"imdb_id": "tt0120737", "title": "Home"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"] == "Provide either imdb_id or title/year, not both"
    assert calls == []


def test_title_search_apply_requires_payload(client, auth_headers, sample_job):
    """
    CHECK an empty body or a body without imdb_id/title is rejected with 400
    data check:
        status: 400
        success: False
    """
    response = client.post(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False

    response = client.post(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
        json={"bogus": "value"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"] == "Provide imdb_id or title"


def test_title_search_apply_rejects_invalid_year(client, auth_headers, sample_job):
    """
    CHECK the year of a custom title must be a digit string of max 4 characters
    data check:
        status: 400 for non-numeric and overlong values
        success: False
    """
    for bad_year in ("abcd", "20155", None, True):
        response = client.post(
            f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
            json={"title": "My Custom Title", "year": bad_year},
            headers=auth_headers,
        )
        assert response.status_code == 400, f"year={bad_year!r} should be rejected"
        body = response.get_json()
        assert body["success"] is False
        assert body["error"] == "Invalid value for field: year"


def test_title_search_apply_job_not_found(client, auth_headers):
    """
    CHECK applying metadata for a missing job returns 404
    data check:
        status: 404
    """
    response = client.post(
        "/api/v1/jobs/999999/titlesearch",
        json={"title": "Nope"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_title_search_apply_requires_auth(client, sample_job):
    """
    CHECK applying metadata without a bearer token returns 401
    data check:
        status: 401
        success: False
    """
    response = client.post(
        f"/api/v1/jobs/{sample_job.job_id}/titlesearch",
        json={"title": "No Auth"},
    )
    assert response.status_code == 401
    assert response.get_json()["success"] is False
