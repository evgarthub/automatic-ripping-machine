"""Tests for Milestone 3 B2: MakeMKV + FFmpeg progress emission + tool tagging"""
import os
import sys
import subprocess as _real_subprocess
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _make_job():
    job = MagicMock()
    job.progress = None
    job.progress_round = None
    job.eta = None
    job.progress_updated_at = None
    job.stage = "ripping"
    job.status = "ripping"
    job.job_id = 1
    return job


class TestMakeMKVProgressEmission:
    """Test PRGV/PRGC parsing triggers emit_job_progress."""

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.makemkv.subprocess.Popen")
    @patch("arm.ripper.makemkv.shutil.which", return_value="/usr/bin/makemkvcon")
    def test_prgv_emits_progress(self, mock_which, mock_popen, mock_emit, app):
        from arm.ripper.makemkv import run, OutputType

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = [
            "PRGV:500,1000,1000\n",
            "MSG:1005,0,1,\"MakeMKV started\"\n",
        ]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        job = _make_job()
        list(run(["info", "disc:0"], OutputType.MSG, job=job))

        mock_emit.assert_called()
        args = mock_emit.call_args
        progress_val = args[0][1]
        assert progress_val == 50.0

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.makemkv.subprocess.Popen")
    @patch("arm.ripper.makemkv.shutil.which", return_value="/usr/bin/makemkvcon")
    def test_prgv_clamped_0_100(self, mock_which, mock_popen, mock_emit, app):
        from arm.ripper.makemkv import run, OutputType

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = [
            "PRGV:1500,1000,1000\n",
        ]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        job = _make_job()
        list(run(["info", "disc:0"], OutputType.MSG, job=job))

        mock_emit.assert_called()
        args = mock_emit.call_args
        progress_val = args[0][1]
        assert progress_val == 100.0

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.makemkv.subprocess.Popen")
    @patch("arm.ripper.makemkv.shutil.which", return_value="/usr/bin/makemkvcon")
    def test_prgc_updates_stage(self, mock_which, mock_popen, mock_emit, app):
        from arm.ripper.makemkv import run, OutputType

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = [
            "PRGC:1,0,\"Opening disc\"\n",
            "PRGV:100,1000,1000\n",
        ]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        job = _make_job()
        list(run(["info", "disc:0"], OutputType.MSG, job=job))

        assert job.stage == "Opening disc"

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.makemkv.subprocess.Popen")
    @patch("arm.ripper.makemkv.shutil.which", return_value="/usr/bin/makemkvcon")
    def test_no_emit_when_job_none(self, mock_which, mock_popen, mock_emit, app):
        from arm.ripper.makemkv import run, OutputType

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = [
            "PRGV:500,1000,1000\n",
        ]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        list(run(["info", "disc:0"], OutputType.MSG))

        mock_emit.assert_not_called()


class TestMakeMKVTagging:
    """Test [MKV] tag prefix on logged lines."""

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.makemkv.subprocess.Popen")
    @patch("arm.ripper.makemkv.shutil.which", return_value="/usr/bin/makemkvcon")
    def test_non_bracket_lines_get_mkv_tag(self, mock_which, mock_popen, mock_emit, app):
        from arm.ripper.makemkv import run, OutputType

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = [
            "PRGV:500,1000,1000\n",
        ]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        job = _make_job()
        with patch("arm.ripper.makemkv.logging") as mock_log:
            list(run(["info", "disc:0"], OutputType.MSG, job=job))
            debug_calls = [c for c in mock_log.debug.call_args_list if "[MKV]" in str(c)]
            assert len(debug_calls) > 0

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.makemkv.subprocess.Popen")
    @patch("arm.ripper.makemkv.shutil.which", return_value="/usr/bin/makemkvcon")
    def test_bracket_lines_not_double_tagged(self, mock_which, mock_popen, mock_emit, app):
        from arm.ripper.makemkv import run, OutputType

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = [
            "[msg] some message\n",
        ]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        job = _make_job()
        with patch("arm.ripper.makemkv.logging") as mock_log:
            list(run(["info", "disc:0"], OutputType.MSG, job=job))
            debug_calls = [c for c in mock_log.debug.call_args_list if "[MKV]" in str(c)]
            assert len(debug_calls) == 0


class TestFFmpegProgressEmission:
    """Test FFmpeg progress pipe parsing and emit_job_progress."""

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.ffmpeg.subprocess.Popen")
    @patch("arm.ripper.ffmpeg.subprocess.check_output", return_value=b"60.0\n")
    @patch("arm.ripper.ffmpeg.correct_ffmpeg_settings", return_value=("-c:v libx264", "-c:a aac"))
    def test_out_time_us_parsing(self, mock_settings, mock_check, mock_popen, mock_emit, app):
        from arm.ripper.ffmpeg import run_transcode_cmd

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = [
            "out_time_us=30000000\n",
            "progress=continue\n",
        ]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        job = _make_job()
        run_transcode_cmd("/src/file.mkv", "/out/file.mp4", job)

        mock_emit.assert_called()
        args = mock_emit.call_args
        percentage = args[0][1]
        assert abs(percentage - 50.0) < 0.01

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.ffmpeg.subprocess.Popen")
    @patch("arm.ripper.ffmpeg.subprocess.check_output", return_value=b"60.0\n")
    @patch("arm.ripper.ffmpeg.correct_ffmpeg_settings", return_value=("-c:v libx264", "-c:a aac"))
    def test_time_fallback_parsing(self, mock_settings, mock_check, mock_popen, mock_emit, app):
        from arm.ripper.ffmpeg import run_transcode_cmd

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = [
            "frame=  100 fps= 30 size=   1024kB time=00:00:30.00 bitrate= 279.7kbits/s\n",
        ]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        job = _make_job()
        run_transcode_cmd("/src/file.mkv", "/out/file.mp4", job)

        mock_emit.assert_called()
        args = mock_emit.call_args
        percentage = args[0][1]
        assert abs(percentage - 50.0) < 0.01

    @patch("time.monotonic")
    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.ffmpeg.subprocess.Popen")
    @patch("arm.ripper.ffmpeg.subprocess.check_output", return_value=b"60.0\n")
    @patch("arm.ripper.ffmpeg.correct_ffmpeg_settings", return_value=("-c:v libx264", "-c:a aac"))
    def test_eta_calculation(self, mock_settings, mock_check, mock_popen, mock_emit, mock_mono, app):
        from arm.ripper.ffmpeg import run_transcode_cmd

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = [
            "out_time_us=30000000\n",
        ]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        mock_mono.side_effect = [0.0, 10.0]

        job = _make_job()
        run_transcode_cmd("/src/file.mkv", "/out/file.mp4", job)

        args = mock_emit.call_args
        eta = args[1].get("eta")
        assert eta is not None
        assert ":" in str(eta)

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.ffmpeg.subprocess.Popen")
    @patch("arm.ripper.ffmpeg.subprocess.check_output", return_value=b"60.0\n")
    @patch("arm.ripper.ffmpeg.correct_ffmpeg_settings", return_value=("-c:v libx264", "-c:a aac"))
    def test_progress_pipe_always_included(self, mock_settings, mock_check, mock_popen, mock_emit, app):
        from arm.ripper.ffmpeg import run_transcode_cmd

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = []
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        job = _make_job()
        run_transcode_cmd("/src/file.mkv", "/out/file.mp4", job)

        cmd_str = mock_popen.call_args[0][0]
        assert "-progress" in cmd_str


class TestFFmpegTagging:
    """Test [FFMPEG] tag prefix on logged lines."""

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.ffmpeg.subprocess.Popen")
    @patch("arm.ripper.ffmpeg.subprocess.check_output", return_value=b"60.0\n")
    @patch("arm.ripper.ffmpeg.correct_ffmpeg_settings", return_value=("-c:v libx264", "-c:a aac"))
    def test_output_lines_get_ffmpeg_tag(self, mock_settings, mock_check, mock_popen, mock_emit, app):
        from arm.ripper.ffmpeg import run_transcode_cmd

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = [
            "out_time_us=30000000\n",
            "progress=continue\n",
        ]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        job = _make_job()
        with patch("arm.ripper.ffmpeg.logging") as mock_log:
            run_transcode_cmd("/src/file.mkv", "/out/file.mp4", job)
            debug_calls = [c for c in mock_log.debug.call_args_list if "[FFMPEG]" in str(c)]
            assert len(debug_calls) > 0

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.ffmpeg.subprocess.Popen")
    @patch("arm.ripper.ffmpeg.subprocess.check_output", return_value=b"60.0\n")
    @patch("arm.ripper.ffmpeg.correct_ffmpeg_settings", return_value=("-c:v libx264", "-c:a aac"))
    def test_bracket_lines_not_double_tagged(self, mock_settings, mock_check, mock_popen, mock_emit, app):
        from arm.ripper.ffmpeg import run_transcode_cmd

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = [
            "[some_tag] data\n",
        ]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        job = _make_job()
        with patch("arm.ripper.ffmpeg.logging") as mock_log:
            run_transcode_cmd("/src/file.mkv", "/out/file.mp4", job)
            debug_calls = [c for c in mock_log.debug.call_args_list if "[FFMPEG]" in str(c)]
            assert len(debug_calls) == 0


class TestMakeMKVCallerIntegration:
    """Test that callers pass job=job to run()."""

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.makemkv.subprocess.Popen")
    @patch("arm.ripper.makemkv.shutil.which", return_value="/usr/bin/makemkvcon")
    def test_makemkv_backup_passes_job(self, mock_which, mock_popen, mock_emit, app):
        from arm.ripper.makemkv import makemkv_backup

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = ["MSG:1005,0,1,\"started\"\n"]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        job = _make_job()
        job.config.MKV_ARGS = ""
        job.config.MINLENGTH = "300"
        job.drive.mdisc = 0
        job.devpath = "/dev/sr0"

        with patch("arm.ripper.makemkv.os.path.exists", return_value=True), \
             patch("arm.ripper.makemkv.logging"):
            makemkv_backup(job, "/tmp/raw")

        mock_popen.assert_called()

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.makemkv.subprocess.Popen")
    @patch("arm.ripper.makemkv.shutil.which", return_value="/usr/bin/makemkvcon")
    def test_process_single_tracks_passes_job(self, mock_which, mock_popen, mock_emit, app):
        from arm.ripper.makemkv import process_single_tracks

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = ["MSG:1005,0,1,\"started\"\n"]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        job = _make_job()
        job.config.MKV_ARGS = ""
        job.config.MINLENGTH = "300"
        job.config.MAXLENGTH = "99999"
        job.devpath = "/dev/sr0"

        track = MagicMock()
        track.process = True
        track.track_number = "1"
        track.length = 500
        track.filename = "title_t01.mkv"
        job.tracks = [track]
        job.no_of_titles = 2

        with patch("arm.ripper.makemkv.logging"):
            process_single_tracks(job, "/tmp/raw", "auto")

        mock_popen.assert_called()


class TestFFmpegNoDurationFallback:
    """Test that FFmpeg still runs when duration probe fails."""

    @patch("arm.ripper.progress.emit_job_progress")
    @patch("arm.ripper.ffmpeg.subprocess.Popen")
    @patch("arm.ripper.ffmpeg.subprocess.check_output",
           side_effect=_real_subprocess.CalledProcessError(1, "ffprobe"))
    @patch("arm.ripper.ffmpeg.correct_ffmpeg_settings", return_value=("-c:v libx264", "-c:a aac"))
    def test_no_duration_no_emit(self, mock_settings, mock_check, mock_popen, mock_emit, app):
        from arm.ripper.ffmpeg import run_transcode_cmd

        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = ["out_time_us=30000000\n"]
        proc.__enter__ = MagicMock(return_value=proc)
        proc.__exit__ = MagicMock(return_value=False)
        mock_popen.return_value = proc

        job = _make_job()
        run_transcode_cmd("/src/file.mkv", "/out/file.mp4", job)

        mock_emit.assert_not_called()
