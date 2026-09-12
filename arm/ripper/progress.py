import logging
from datetime import datetime

from arm.ripper.utils import database_updater


def emit_job_progress(job, progress, stage, eta=None):
    """Emit a progress update to the database with throttling.

    Returns True if the database was written, False if skipped.
    """
    now = datetime.utcnow()
    if job.progress_updated_at is not None:
        elapsed = (now - job.progress_updated_at).total_seconds()
        if elapsed < 2 and stage == job.stage and abs(progress - (job.progress or 0)) < 5:
            return False
    update = {
        "progress": progress,
        "progress_round": f"{progress:.1f}",
        "stage": stage,
        "progress_updated_at": now,
        "eta": eta,
    }
    if stage != job.stage:
        update["status"] = stage
    return database_updater(update, job)
