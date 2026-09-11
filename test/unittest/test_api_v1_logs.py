"""
Unit tests for GET /api/v1/logs and GET /api/v1/logs/<name>
"""
import os

import pytest

import arm.config.config as cfg


LOG_CONTENT = (
    "ARM: checking for disc\n"
    "mkv mkv.mkv: first pass\n"
    "ARM: starting rip\n"
    "transcode step 47%\n"
    "ARM: job finished\n"
)


@pytest.fixture(autouse=True)
def log_dir():
    """Temporary flat log files inside the isolated LOGPATH"""
    path = cfg.arm_config["LOGPATH"]
    os.makedirs(path, exist_ok=True)
    for name in ("older.log", "newer.log"):
        with open(os.path.join(path, name), "w", encoding="utf-8", newline="\n") as log_file:
            log_file.write(LOG_CONTENT)
    os.utime(os.path.join(path, "older.log"), (1000000, 1000000))
    os.utime(os.path.join(path, "newer.log"), (2000000, 2000000))
    yield path
    for name in ("older.log", "newer.log"):
        try:
            os.remove(os.path.join(path, name))
        except OSError:
            pass


def test_list_logs_newest_first(client, auth_headers):
    """
    CHECK the log list contains name/size_bytes/modified sorted newest first
    data check:
        status: 200
        success: True
        names: [newer.log, older.log] in that order
        size_bytes: matches file size
    """
    response = client.get("/api/v1/logs", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    names = [entry["name"] for entry in body["data"]]
    assert names == ["newer.log", "older.log"]
    for entry in body["data"]:
        assert set(entry.keys()) == {"name", "size_bytes", "modified"}
        assert entry["size_bytes"] == len(LOG_CONTENT.encode("utf-8"))


def test_list_logs_requires_auth(client):
    """
    CHECK listing logs without a bearer token returns 401
    data check:
        status: 401
    """
    response = client.get("/api/v1/logs")
    assert response.status_code == 401


def test_read_log_full(client, auth_headers):
    """
    CHECK mode=full returns the whole file as text/plain
    data check:
        status: 200
        mimetype: text/plain
        body: identical to file content
    """
    response = client.get("/api/v1/logs/newer.log?mode=full", headers=auth_headers)
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert response.get_data(as_text=True) == LOG_CONTENT


def test_read_log_default_mode_is_full(client, auth_headers):
    """
    CHECK omitting mode defaults to the full file
    data check:
        status: 200
        body: full content
    """
    response = client.get("/api/v1/logs/newer.log", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_data(as_text=True) == LOG_CONTENT


def test_read_log_armcat_filters_arm_lines(client, auth_headers):
    """
    CHECK mode=armcat returns only ARM: lines like the legacy generator
    data check:
        status: 200
        body: the three ARM: lines only
    """
    response = client.get("/api/v1/logs/newer.log?mode=armcat", headers=auth_headers)
    assert response.status_code == 200
    expected = "".join(line for line in LOG_CONTENT.splitlines(keepends=True) if "ARM:" in line)
    assert response.get_data(as_text=True) == expected


def test_read_log_tail_lines(client, auth_headers):
    """
    CHECK lines=N returns only the last N lines of the filtered content
    data check:
        status: 200
        body: last 2 lines of the full file
    """
    response = client.get("/api/v1/logs/newer.log?mode=full&lines=2", headers=auth_headers)
    assert response.status_code == 200
    expected = "".join(LOG_CONTENT.splitlines(keepends=True)[-2:])
    assert response.get_data(as_text=True) == expected


def test_read_log_armcat_tail_lines(client, auth_headers):
    """
    CHECK lines=N applies after the armcat filter
    data check:
        status: 200
        body: last ARM: line only
    """
    response = client.get("/api/v1/logs/newer.log?mode=armcat&lines=1", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "ARM: job finished\n"


def test_read_log_invalid_lines_returns_400(client, auth_headers):
    """
    CHECK a non-numeric or non-positive lines value returns 400
    data check:
        status: 400
    """
    response = client.get("/api/v1/logs/newer.log?mode=full&lines=abc", headers=auth_headers)
    assert response.status_code == 400
    response = client.get("/api/v1/logs/newer.log?mode=full&lines=0", headers=auth_headers)
    assert response.status_code == 400


def test_read_log_bad_mode_returns_400(client, auth_headers):
    """
    CHECK an unknown mode returns 400 like the legacy logreader
    data check:
        status: 400
    """
    response = client.get("/api/v1/logs/newer.log?mode=nonsense", headers=auth_headers)
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_read_log_unknown_file_returns_404(client, auth_headers):
    """
    CHECK a logfile that does not exist in LOGPATH returns 404
    data check:
        status: 404
    """
    response = client.get("/api/v1/logs/nope.log?mode=full", headers=auth_headers)
    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_read_log_download_attachment(client, auth_headers):
    """
    CHECK mode=download sends the file as an attachment
    data check:
        status: 200
        Content-Disposition: attachment with the filename
        body: full content
    """
    response = client.get("/api/v1/logs/newer.log?mode=download", headers=auth_headers)
    assert response.status_code == 200
    assert "attachment" in response.headers.get("Content-Disposition", "")
    assert "newer.log" in response.headers.get("Content-Disposition", "")
    assert response.get_data(as_text=True) == LOG_CONTENT


def test_read_log_traversal_slash_rejected(client, auth_headers):
    """
    CHECK a traversal attempt with an encoded slash cannot leave LOGPATH
    data check:
        status: 400 or 404, never 200
    """
    response = client.get("/api/v1/logs/..%2Fnewer.log?mode=full", headers=auth_headers)
    assert response.status_code in (400, 404)


def test_read_log_traversal_dotdot_rejected(client, auth_headers):
    """
    CHECK a plain .. name is rejected
    data check:
        status: 400
    """
    response = client.get("/api/v1/logs/..?mode=full", headers=auth_headers)
    assert response.status_code == 400


def test_read_log_traversal_backslash_rejected(client, auth_headers, log_dir):
    """
    CHECK a Windows-style ..\\ traversal is rejected by the basename check
    data check:
        status: 400
    """
    secret = os.path.join(os.path.dirname(log_dir.rstrip("/\\")), "secret.log")
    with open(secret, "w", encoding="utf-8") as secret_file:
        secret_file.write("secret")
    try:
        response = client.get("/api/v1/logs/..%5Csecret.log?mode=full", headers=auth_headers)
        assert response.status_code == 400
    finally:
        os.remove(secret)
