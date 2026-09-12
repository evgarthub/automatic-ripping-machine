"""Tests for Milestone 3 B3: HandBrake + abcde streaming + tool tagging"""
import os
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestHandbrakeProgress:
    """Popen streaming + tee + progress parsing for HandBrake."""

    def _make_job(self):
        job = MagicMock()
        job.progress = None
        job.progress_round = None
        job.eta = None
        job.progress_updated_at = None
        job.stage = None
        job.job_id = 1
        return job

    def _make_track(self):
        track = MagicMock()
        track.status = None
        track.error = None
        return track

    @patch("arm.ripper.progress.emit_job_progress")
    def test_encoding_progress_and_eta(self, mock_emit):
        from arm.ripper.handbrake import run_handbrake_command

        job = self._make_job()
        track = self._make_track()
        lines = [
            "Encoding: task 1 of 3, 50.25 %"
            " (250.00 fps, avg 120.00 fps, ETA 01:23:45)\r\n",
            "Encoding: task 2 of 3, 80.00 %"
            " (300.00 fps, avg 150.00 fps, ETA 00:10:20)\r\n",
        ]

        mock_proc = MagicMock()
        mock_proc.stdout = iter(lines)
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as tmp:
            logfile = tmp.name
        try:
            with patch("subprocess.Popen", return_value=mock_proc):
                run_handbrake_command(
                    "HandBrakeCLI -i /tmp/src -o /tmp/out", job, logfile, track=track
                )

            assert track.status == "success"
            assert mock_emit.call_count >= 1

            first_call = mock_emit.call_args_list[0]
            progress_val = first_call[0][1]
            assert 50.2 < progress_val < 50.3
            assert first_call[1]["eta"] == "01:23:45"

            second_call = mock_emit.call_args_list[1]
            progress_val2 = second_call[0][1]
            assert 79.9 < progress_val2 < 80.1
            assert second_call[1]["eta"] == "00:10:20"
        finally:
            os.unlink(logfile)

    @patch("arm.ripper.progress.emit_job_progress")
    def test_processing_track_overall_progress(self, mock_emit):
        from arm.ripper.handbrake import run_handbrake_command

        job = self._make_job()
        lines = [
            "Processing track #2 of 5\r\n",
            "Encoding: task 1 of 1, 75.00 %"
            " (200.00 fps, ETA 00:05:30)\r\n",
        ]

        mock_proc = MagicMock()
        mock_proc.stdout = iter(lines)
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as tmp:
            logfile = tmp.name
        try:
            with patch("subprocess.Popen", return_value=mock_proc):
                run_handbrake_command(
                    "HandBrakeCLI -i /tmp/src -o /tmp/out", job, logfile
                )

            calls_with_track = [c for c in mock_emit.call_args_list
                                if "Track 2/5" in c[1].get("stage", "")]
            assert len(calls_with_track) == 1
            progress = calls_with_track[0][0][1]
            expected = (2 + 75.0 / 100) / 5 * 100
            assert abs(progress - expected) < 0.01
        finally:
            os.unlink(logfile)

    def test_tee_writes_tagged_output_to_logfile(self):
        from arm.ripper.handbrake import run_handbrake_command

        job = self._make_job()
        lines = ["Scan: reading title 1\r\n", "Encoding: done\r\n"]

        mock_proc = MagicMock()
        mock_proc.stdout = iter(lines)
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as tmp:
            logfile = tmp.name
        try:
            with patch("subprocess.Popen", return_value=mock_proc):
                run_handbrake_command(
                    "HandBrakeCLI -i /tmp/src -o /tmp/out", job, logfile
                )

            with open(logfile, "r", encoding="utf-8") as f:
                content = f.read()
            assert "[HB]Scan: reading title 1" in content
            assert "[HB]Encoding: done" in content
        finally:
            os.unlink(logfile)

    def test_failure_sets_track_status_and_raises(self):
        from arm.ripper.handbrake import run_handbrake_command

        job = self._make_job()
        track = self._make_track()

        mock_proc = MagicMock()
        mock_proc.stdout = iter(["Error: something failed\r\n"])
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 1

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as tmp:
            logfile = tmp.name
        try:
            with patch("subprocess.Popen", return_value=mock_proc):
                with pytest.raises(subprocess.CalledProcessError) as exc_info:
                    run_handbrake_command(
                        "HandBrakeCLI -i /tmp/src -o /tmp/out",
                        job, logfile, track=track, track_number=3,
                    )
                assert exc_info.value.returncode == 1
            assert track.status == "fail"
            assert "title 3" in track.error
        finally:
            os.unlink(logfile)


class TestAbcdeProgress:
    """Popen streaming + tee + track progress for abcde."""

    def _make_job(self):
        job = MagicMock()
        job.progress = None
        job.progress_round = None
        job.eta = None
        job.progress_updated_at = None
        job.stage = None
        job.job_id = 1
        job.devpath = "/dev/sr0"
        job.config.LOGPATH = tempfile.gettempdir()
        job.disctype = "music"
        return job

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.utils.database_updater")
    def test_track_progress_parsing(self, mock_db, mock_emit):
        from arm.ripper.utils import rip_music

        job = self._make_job()
        lines = [
            "(track  1 of 12): /dev/sr0\r\n",
            "(track  3 of 12): /dev/sr0\r\n",
            "Finished.\r\n",
        ]

        mock_proc = MagicMock()
        mock_proc.stdout = iter(lines)
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("os.path.isfile", return_value=False):
                result = rip_music(job, "test.log")

        assert result is True
        track_calls = [c for c in mock_emit.call_args_list
                       if "Track" in c[1].get("stage", "")]
        assert len(track_calls) == 2

        first = track_calls[0]
        assert abs(first[0][1] - (1 / 12 * 100)) < 0.01
        assert first[1]["stage"] == "Track 1/12"

        second = track_calls[1]
        assert abs(second[0][1] - (3 / 12 * 100)) < 0.01
        assert second[1]["stage"] == "Track 3/12"

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.utils.database_updater")
    def test_abcde_tag_in_logfile(self, mock_db, mock_emit):
        from arm.ripper.utils import rip_music

        job = self._make_job()
        lines = ["(track  1 of 5): /dev/sr0\r\n", "Finished.\r\n"]

        mock_proc = MagicMock()
        mock_proc.stdout = iter(lines)
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0

        logpath = os.path.join(tempfile.gettempdir(), "test_abcde_tag.log")
        job.config.LOGPATH = tempfile.gettempdir()

        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("os.path.isfile", return_value=False):
                rip_music(job, "test_abcde_tag.log")

        try:
            with open(logpath, "r", encoding="utf-8") as f:
                content = f.read()
            assert "[ABCDE](track  1 of 5): /dev/sr0" in content
            assert "[ABCDE]Finished." in content
        finally:
            if os.path.exists(logpath):
                os.unlink(logpath)

    @patch("arm.ripper.utils.database_updater")
    def test_no_finished_sets_failure(self, mock_db):
        from arm.ripper.utils import rip_music

        job = self._make_job()
        lines = ["(track  1 of 5): /dev/sr0\r\n", "Some other output\r\n"]

        mock_proc = MagicMock()
        mock_proc.stdout = iter(lines)
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("os.path.isfile", return_value=False):
                result = rip_music(job, "test_no_finished.log")

        assert result is False
        failure_calls = [c for c in mock_db.call_args_list
                         if c[0][0].get("status") == "fail"]
        assert len(failure_calls) == 1
        assert "incomplete" in failure_calls[0][0][0]["errors"]

    @patch("arm.ripper.utils.database_updater")
    def test_nonzero_exit_sets_failure(self, mock_db):
        from arm.ripper.utils import rip_music

        job = self._make_job()
        lines = ["abcde: error occurred\r\n"]

        mock_proc = MagicMock()
        mock_proc.stdout = iter(lines)
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 1

        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("os.path.isfile", return_value=False):
                result = rip_music(job, "test_fail.log")

        assert result is False
        failure_calls = [c for c in mock_db.call_args_list
                         if c[0][0].get("status") == "fail"]
        assert len(failure_calls) == 1


class TestBuildHandbrakeCommand:
    """Verify build_handbrake_command no longer appends shell redirect."""

    def test_no_redirect_in_command(self):
        from arm.ripper.handbrake import build_handbrake_command

        cmd = build_handbrake_command(
            "/dev/dvd", "/tmp/out.mkv", "Fast", "--quiet", "/tmp/log.txt"
        )
        assert ">>" not in cmd
        assert "2>&1" not in cmd
        assert "HandBrakeCLI" in cmd or "hb" in cmd.lower()
