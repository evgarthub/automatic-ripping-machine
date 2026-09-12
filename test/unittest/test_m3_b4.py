"""Tests for Milestone 3 B4: UI push + watchdog + delete process_logfile"""
import os
import sys
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest
from sqlalchemy import text

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _insert_test_job(app, **overrides):
    """Insert a job row directly and return its job_id."""
    defaults = dict(
        job_id=None, status="ripping", stage="ripping", progress=50,
        progress_round="50.0", eta="00:10:00", progress_updated_at=None,
        title="Test", title_auto="Test", title_manual=None,
        year="2024", year_auto="2024", year_manual=None,
        video_type="movie", video_type_auto="movie", video_type_manual=None,
        imdb_id="tt123", imdb_id_auto="tt123", imdb_id_manual=None,
        poster_url="", poster_url_auto="", poster_url_manual=None,
        devpath="/dev/sr0", disctype="dvd", label="TEST",
        hasnicetitle=1, pid=99999, pid_hash=11111, logfile="test.log",
        ejected=0, updated=0, manual_start=0, manual_mode=0,
        is_iso=0, no_of_titles=1, errors=None, crc_id=None,
        arm_version="1.0", start_time=datetime.now(), stop_time=None,
        job_length="", mountpoint=""
    )
    defaults.update(overrides)
    cols = ", ".join(defaults.keys())
    placeholders = ", ".join([f":{k}" for k in defaults.keys()])
    with app.app_context():
        from arm.ui import db
        result = db.session.execute(
            text(f"INSERT INTO job ({cols}) VALUES ({placeholders})"),
            defaults
        )
        db.session.commit()
        return result.lastrowid


class TestProgressPoller:
    """Test background progress poller emits correct events on state changes."""

    @patch("arm.ui.api.v1.websockets.emit_job_progress")
    @patch("arm.ui.api.v1.websockets.emit_job_status_change")
    @patch("arm.ui.api.v1.websockets.emit_job_completed")
    @patch("arm.ui.api.v1.websockets._last_emitted", {})
    def test_emits_on_first_poll(self, mock_completed, mock_status, mock_progress, app):
        from arm.ui.api.v1.websockets import _check_active_jobs
        from arm.models.job import Job

        job = MagicMock(spec=Job)
        job.job_id = 999
        job.progress = 42
        job.stage = "ripping"
        job.status = "ripping"
        job.progress_round = "42.0"
        job.eta = "00:10:00"
        job.finished = False

        with patch("arm.ui.api.v1.websockets.Job") as MockJob:
            MockJob.query.filter.return_value.all.return_value = [job]
            _check_active_jobs()

        mock_progress.assert_called()
        args = mock_progress.call_args[0]
        assert args[0] == 999
        assert args[1]['progress'] == 42

    @patch("arm.ui.api.v1.websockets.emit_job_progress")
    @patch("arm.ui.api.v1.websockets.emit_job_status_change")
    @patch("arm.ui.api.v1.websockets.emit_job_completed")
    @patch("arm.ui.api.v1.websockets._last_emitted", {888: {'progress': 50, 'stage': 'ripping', 'status': 'ripping'}})
    def test_no_emit_when_state_unchanged(self, mock_completed, mock_status, mock_progress, app):
        from arm.ui.api.v1.websockets import _check_active_jobs

        job = MagicMock()
        job.job_id = 888
        job.progress = 50
        job.stage = "ripping"
        job.status = "ripping"
        job.progress_round = "50.0"
        job.eta = "00:10:00"
        job.finished = False

        with patch("arm.ui.api.v1.websockets.Job") as MockJob:
            MockJob.query.filter.return_value.all.return_value = [job]
            _check_active_jobs()

        mock_progress.assert_not_called()
        mock_status.assert_not_called()

    @patch("arm.ui.api.v1.websockets.emit_job_progress")
    @patch("arm.ui.api.v1.websockets.emit_job_status_change")
    @patch("arm.ui.api.v1.websockets.emit_job_completed")
    @patch("arm.ui.api.v1.websockets._last_emitted", {777: {'progress': 50, 'stage': 'ripping', 'status': 'ripping'}})
    def test_emits_progress_on_change(self, mock_completed, mock_status, mock_progress, app):
        from arm.ui.api.v1.websockets import _check_active_jobs

        job = MagicMock()
        job.job_id = 777
        job.progress = 75
        job.stage = "transcoding"
        job.status = "ripping"
        job.progress_round = "75.0"
        job.eta = "00:05:00"
        job.finished = False

        with patch("arm.ui.api.v1.websockets.Job") as MockJob:
            MockJob.query.filter.return_value.all.return_value = [job]
            _check_active_jobs()

        mock_progress.assert_called()

    @patch("arm.ui.api.v1.websockets.emit_job_progress")
    @patch("arm.ui.api.v1.websockets.emit_job_status_change")
    @patch("arm.ui.api.v1.websockets.emit_job_completed")
    @patch("arm.ui.api.v1.websockets._last_emitted", {666: {'progress': 50, 'stage': 'ripping', 'status': 'ripping'}})
    def test_emits_status_on_change(self, mock_completed, mock_status, mock_progress, app):
        from arm.ui.api.v1.websockets import _check_active_jobs

        job = MagicMock()
        job.job_id = 666
        job.progress = 50
        job.stage = "ripping"
        job.status = "transcoding"
        job.progress_round = "50.0"
        job.eta = "00:10:00"
        job.finished = False

        with patch("arm.ui.api.v1.websockets.Job") as MockJob:
            MockJob.query.filter.return_value.all.return_value = [job]
            _check_active_jobs()

        mock_status.assert_called_once()
        args = mock_status.call_args[0]
        assert args == (666, 'ripping', 'transcoding')

    @patch("arm.ui.api.v1.websockets.emit_job_progress")
    @patch("arm.ui.api.v1.websockets.emit_job_status_change")
    @patch("arm.ui.api.v1.websockets.emit_job_completed")
    @patch("arm.ui.api.v1.websockets._last_emitted", {})
    def test_emits_completed_on_success(self, mock_completed, mock_status, mock_progress, app):
        from arm.ui.api.v1.websockets import _check_active_jobs

        job = MagicMock()
        job.job_id = 555
        job.progress = 100
        job.stage = "done"
        job.status = "success"
        job.progress_round = "100.0"
        job.eta = "00:00:00"
        job.finished = True

        with patch("arm.ui.api.v1.websockets.Job") as MockJob:
            MockJob.query.filter.return_value.all.return_value = [job]
            _check_active_jobs()

        mock_completed.assert_called_once()
        args = mock_completed.call_args[0]
        assert args == (555, True)

    @patch("arm.ui.api.v1.websockets.emit_job_progress")
    @patch("arm.ui.api.v1.websockets.emit_job_status_change")
    @patch("arm.ui.api.v1.websockets.emit_job_completed")
    @patch("arm.ui.api.v1.websockets._last_emitted", {})
    def test_poller_survives_db_error(self, mock_completed, mock_status, mock_progress, app):
        from arm.ui.api.v1.websockets import _check_active_jobs

        with patch("arm.ui.api.v1.websockets.Job") as MockJob:
            MockJob.query.filter.return_value.all.side_effect = Exception("DB locked")
            _check_active_jobs()

        mock_progress.assert_not_called()

    @patch("arm.ui.api.v1.websockets.emit_job_progress")
    @patch("arm.ui.api.v1.websockets.emit_job_status_change")
    @patch("arm.ui.api.v1.websockets.emit_job_completed")
    @patch("arm.ui.api.v1.websockets._last_emitted", {444: {'progress': 50, 'stage': 'ripping', 'status': 'ripping'}})
    def test_cleans_stale_entries(self, mock_completed, mock_status, mock_progress, app):
        from arm.ui.api.v1.websockets import _check_active_jobs, _last_emitted

        with patch("arm.ui.api.v1.websockets.Job") as MockJob:
            MockJob.query.filter.return_value.all.return_value = []
            _check_active_jobs()

        assert 444 not in _last_emitted


class TestWatchdog:
    """Test watchdog marks dead/invalid jobs as failed with notifications."""

    @pytest.fixture(autouse=True)
    def _clean_jobs(self, app):
        with app.app_context():
            from arm.ui import db
            db.session.execute(text("DELETE FROM job"))
            db.session.commit()
        yield
        with app.app_context():
            from arm.ui import db
            db.session.execute(text("DELETE FROM job"))
            db.session.commit()

    @patch("arm.ripper.utils.psutil.pid_exists", return_value=False)
    def test_dead_pid_marks_failed(self, mock_pid_exists, app):
        from arm.ripper.utils import watchdog_check
        from arm.ui import db

        job_id = _insert_test_job(app, pid=99999, pid_hash=11111, status="ripping")

        with app.app_context():
            with patch("arm.ripper.utils.database_updater") as mock_updater, \
                 patch("arm.ripper.utils.db.session.add"), \
                 patch("arm.ripper.utils.db.session.commit"):
                watchdog_check()
                mock_updater.assert_called_once()
                call_args = mock_updater.call_args[0]
                assert call_args[0] == {'status': 'fail'}

    @patch("arm.ripper.utils.psutil.pid_exists", return_value=True)
    @patch("arm.ripper.utils.psutil.Process")
    def test_hash_mismatch_marks_failed(self, MockProcess, mock_pid_exists, app):
        from arm.ripper.utils import watchdog_check
        from arm.ui import db

        job_id = _insert_test_job(app, pid=12345, pid_hash=11111, status="ripping")

        mock_proc = MagicMock()
        mock_proc.__hash__ = MagicMock(return_value=22222)
        MockProcess.return_value = mock_proc

        with app.app_context():
            with patch("arm.ripper.utils.database_updater") as mock_updater, \
                 patch("arm.ripper.utils.db.session.add"), \
                 patch("arm.ripper.utils.db.session.commit"):
                watchdog_check()
                mock_updater.assert_called_once()
                call_args = mock_updater.call_args[0]
                assert call_args[0] == {'status': 'fail'}

    @patch("arm.ripper.utils.psutil.pid_exists", return_value=True)
    @patch("arm.ripper.utils.psutil.Process")
    def test_alive_pid_no_mismatch_no_action(self, MockProcess, mock_pid_exists, app):
        from arm.ripper.utils import watchdog_check

        job_id = _insert_test_job(app, pid=12345, pid_hash=33333, status="ripping")

        mock_proc = MagicMock()
        mock_proc.__hash__ = MagicMock(return_value=33333)
        MockProcess.return_value = mock_proc

        with app.app_context():
            with patch("arm.ripper.utils.database_updater") as mock_updater:
                watchdog_check()
                mock_updater.assert_not_called()

    def test_clean_old_jobs_delegates_to_watchdog(self, app):
        from arm.ripper.utils import clean_old_jobs
        with patch("arm.ripper.utils.watchdog_check") as mock_wc:
            clean_old_jobs()
            mock_wc.assert_called_once()


class TestV1ProgressEndpoint:
    """Test that get_job_progress reads from DB columns."""

    def test_progress_reads_from_db(self, client, auth_headers, app):
        job_id = _insert_test_job(
            app, job_id=2001, status="ripping", stage="Transcoding",
            progress=67, progress_round="67.0", eta="00:15:00"
        )

        resp = client.get(
            f'/api/v1/jobs/{job_id}/progress',
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['progress'] == 67
        assert data['data']['stage'] == "Transcoding"
        assert data['data']['eta'] == "00:15:00"
        assert data['data']['status'] == "ripping"


class TestLegacyJsonJoblist:
    """Test that /json?mode=joblist reads from DB columns."""

    def test_joblist_response_shape(self, client, app):
        job_id = _insert_test_job(
            app, status="active", stage="Scanning",
            progress=30, progress_round="30.0", eta="00:20:00",
            title="Legacy Movie", title_auto="Legacy Movie"
        )

        resp = client.get('/json?mode=joblist')
        data = resp.get_json()
        assert data['success'] is True
        assert 'results' in data
        found = False
        for key, val in data['results'].items():
            if val.get('job_id') == str(job_id):
                found = True
                assert val['status'] == 'active'
                break
        assert found


class TestProcessLogfileDeleted:
    """Verify process_logfile and friends are removed."""

    def test_process_logfile_import_raises(self):
        with pytest.raises((ImportError, AttributeError)):
            from arm.ui.json_api import process_logfile  # noqa: F401

    def test_process_makemkv_logfile_import_raises(self):
        with pytest.raises((ImportError, AttributeError)):
            from arm.ui.json_api import process_makemkv_logfile  # noqa: F401

    def test_process_handbrake_logfile_import_raises(self):
        with pytest.raises((ImportError, AttributeError)):
            from arm.ui.json_api import process_handbrake_logfile  # noqa: F401

    def test_process_audio_logfile_import_raises(self):
        with pytest.raises((ImportError, AttributeError)):
            from arm.ui.json_api import process_audio_logfile  # noqa: F401

    def test_read_log_line_import_raises(self):
        with pytest.raises((ImportError, AttributeError)):
            from arm.ui.json_api import read_log_line  # noqa: F401

    def test_calc_process_time_import_raises(self):
        with pytest.raises((ImportError, AttributeError)):
            from arm.ui.json_api import calc_process_time  # noqa: F401
