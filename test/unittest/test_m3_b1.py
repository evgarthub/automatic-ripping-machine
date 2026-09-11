"""Tests for Milestone 3 B1: ripping reliability foundations"""
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestMigrationUpgradeDowngrade:
    """Test migration adds and drops columns correctly."""

    def test_upgrade_adds_columns(self, app):
        with app.app_context():
            from arm.ui import db
            from sqlalchemy import inspect

            inspector = inspect(db.engine)
            columns = {c["name"] for c in inspector.get_columns("job")}
            for col in ("progress", "progress_round", "eta", "progress_updated_at"):
                assert col in columns, f"Column {col} missing after upgrade"

    def test_downgrade_drops_columns(self):
        import sqlalchemy as sa
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from sqlalchemy import create_engine, MetaData

        engine = create_engine("sqlite://")
        with engine.connect() as conn:
            conn.execute(sa.text(
                "CREATE TABLE job (job_id INTEGER PRIMARY KEY, status TEXT, stage TEXT, "
                "progress INTEGER, progress_round TEXT, eta TEXT, progress_updated_at TIMESTAMP)"
            ))
            conn.commit()
            ctx = MigrationContext.configure(conn)
            op = Operations(ctx)
            op.drop_column("job", "progress_updated_at")
            op.drop_column("job", "eta")
            op.drop_column("job", "progress_round")
            op.drop_column("job", "progress")
            meta = MetaData()
            meta.reflect(bind=engine)
            columns = {c.name for c in meta.tables["job"].columns}
            assert "progress" not in columns
            assert "progress_round" not in columns
            assert "eta" not in columns
            assert "progress_updated_at" not in columns


class TestEmitJobProgress:
    """Test throttled emit helper."""

    def _make_job(self):
        job = MagicMock()
        job.progress = None
        job.progress_round = None
        job.eta = None
        job.progress_updated_at = None
        job.stage = "ripping"
        job.status = "ripping"
        job.job_id = 1
        return job

    @patch("arm.ripper.progress.database_updater")
    def test_initial_emit_when_none(self, mock_db, app):
        from arm.ripper.progress import emit_job_progress

        mock_db.return_value = True
        job = self._make_job()
        result = emit_job_progress(job, 10, "ripping")
        assert result is True
        mock_db.assert_called_once()

    @patch("arm.ripper.progress.database_updater")
    def test_throttle_skips_small_increment(self, mock_db, app):
        from arm.ripper.progress import emit_job_progress

        mock_db.return_value = True
        job = self._make_job()
        job.progress_updated_at = datetime.utcnow()
        job.progress = 10
        job.stage = "ripping"
        result = emit_job_progress(job, 12, "ripping")
        assert result is False
        mock_db.assert_not_called()

    @patch("arm.ripper.progress.database_updater")
    def test_stage_change_overrides_throttle(self, mock_db, app):
        from arm.ripper.progress import emit_job_progress

        mock_db.return_value = True
        job = self._make_job()
        job.progress_updated_at = datetime.utcnow()
        job.progress = 10
        job.stage = "ripping"
        result = emit_job_progress(job, 12, "transcoding")
        assert result is True
        mock_db.assert_called_once()

    @patch("arm.ripper.progress.database_updater")
    def test_large_increment_overrides_throttle(self, mock_db, app):
        from arm.ripper.progress import emit_job_progress

        mock_db.return_value = True
        job = self._make_job()
        job.progress_updated_at = datetime.utcnow()
        job.progress = 10
        job.stage = "ripping"
        result = emit_job_progress(job, 20, "ripping")
        assert result is True
        mock_db.assert_called_once()

    @patch("arm.ripper.progress.database_updater")
    def test_elapsed_time_overrides_throttle(self, mock_db, app):
        from arm.ripper.progress import emit_job_progress

        mock_db.return_value = True
        job = self._make_job()
        job.progress_updated_at = datetime.utcnow() - timedelta(seconds=3)
        job.progress = 10
        job.stage = "ripping"
        result = emit_job_progress(job, 12, "ripping")
        assert result is True
        mock_db.assert_called_once()


class TestDatabaseUpdaterFix:
    """Test that exhausted locks return False and log error."""

    @patch("arm.ripper.utils.db")
    def test_exhausted_locks_returns_false(self, mock_db, app):
        from arm.ripper.utils import database_updater

        mock_db.session.commit.side_effect = Exception("database is locked")
        mock_db.session.rollback = MagicMock()
        job = MagicMock()
        job.job_id = 1
        result = database_updater({"status": "ripping"}, job, wait_time=1)
        assert result is False

    @patch("arm.ripper.utils.db")
    def test_exhausted_locks_logs_error(self, mock_db, app, caplog):
        import logging

        from arm.ripper.utils import database_updater

        mock_db.session.commit.side_effect = Exception("database is locked")
        mock_db.session.rollback = MagicMock()
        job = MagicMock()
        job.job_id = 1
        with caplog.at_level(logging.ERROR):
            database_updater({"status": "ripping"}, job, wait_time=1)
        assert "Failed to write" in caplog.text


class TestWALPragma:
    """Test that WAL pragma is applied on engine connect."""

    def test_wal_mode_on_test_db(self, app):
        with app.app_context():
            from arm.ui import db
            from sqlalchemy import text

            result = db.session.execute(text("PRAGMA journal_mode")).scalar()
            assert result == "wal"

    def test_busy_timeout_on_test_db(self, app):
        with app.app_context():
            from arm.ui import db
            from sqlalchemy import text

            result = db.session.execute(text("PRAGMA busy_timeout")).scalar()
            assert result == 30000
