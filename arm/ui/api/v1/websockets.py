"""
WebSocket handlers for real-time updates
"""
import logging
from flask_socketio import emit, join_room, leave_room
from arm.ui import socketio, app, db
from arm.models.job import Job

_last_emitted: dict[int, dict] = {}


def emit_job_progress(job_id, progress_data):
    """Emit job progress update to subscribed clients"""
    room = f'job_{job_id}'
    socketio.emit('job_progress', {
        'job_id': job_id,
        'progress': progress_data
    }, to=room, namespace='/ws/jobs')

    socketio.emit('job_progress', {
        'job_id': job_id,
        'progress': progress_data
    }, to='all_jobs', namespace='/ws/jobs')


def emit_job_status_change(job_id, old_status, new_status):
    """Emit job status change to subscribed clients"""
    room = f'job_{job_id}'
    socketio.emit('job_status_change', {
        'job_id': job_id,
        'old_status': old_status,
        'new_status': new_status
    }, to=room, namespace='/ws/jobs')

    socketio.emit('job_status_change', {
        'job_id': job_id,
        'old_status': old_status,
        'new_status': new_status
    }, to='all_jobs', namespace='/ws/jobs')


def emit_job_completed(job_id, success, message=None):
    """Emit job completion to subscribed clients"""
    room = f'job_{job_id}'
    socketio.emit('job_completed', {
        'job_id': job_id,
        'success': success,
        'message': message
    }, to=room, namespace='/ws/jobs')

    socketio.emit('job_completed', {
        'job_id': job_id,
        'success': success,
        'message': message
    }, to='all_jobs', namespace='/ws/jobs')


def send_job_update(job_id):
    """Send job update to WebSocket clients"""
    try:
        with app.app_context():
            job = Job.query.get(job_id)
            if not job or job.finished:
                return

            progress_data = {
                'job_id': job_id,
                'status': job.status,
                'stage': job.stage or '',
                'progress': job.progress if job.progress is not None else 0,
                'progress_round': job.progress_round or '0',
                'eta': job.eta or 'Unknown',
            }

        emit_job_progress(job_id, progress_data)

    except Exception as e:
        logging.error(f"Error sending job update: {e}")


def _check_active_jobs():
    """Poll active jobs and emit state changes via WebSocket."""
    try:
        with app.app_context():
            active_jobs = Job.query.filter(Job.status.notin_(['fail', 'success'])).all()
            active_ids = set()
            for job in active_jobs:
                job_id = job.job_id
                active_ids.add(job_id)

                current_state = {
                    'progress': job.progress if job.progress is not None else 0,
                    'stage': job.stage or '',
                    'status': job.status,
                }

                prev = _last_emitted.get(job_id)
                if prev is None:
                    emit_job_progress(job_id, {
                        'job_id': job_id,
                        'status': current_state['status'],
                        'stage': current_state['stage'],
                        'progress': current_state['progress'],
                        'progress_round': job.progress_round or '0',
                        'eta': job.eta or 'Unknown',
                    })
                else:
                    if current_state['status'] != prev['status']:
                        emit_job_status_change(job_id, prev['status'], current_state['status'])
                    if (current_state['progress'] != prev['progress']
                            or current_state['stage'] != prev['stage']):
                        emit_job_progress(job_id, {
                            'job_id': job_id,
                            'status': current_state['status'],
                            'stage': current_state['stage'],
                            'progress': current_state['progress'],
                            'progress_round': job.progress_round or '0',
                            'eta': job.eta or 'Unknown',
                        })

                if current_state['progress'] == 100 or current_state['status'] in ('fail', 'success'):
                    emit_job_completed(job_id, current_state['status'] == 'success')

                _last_emitted[job_id] = current_state

            stale = [jid for jid in _last_emitted if jid not in active_ids]
            for jid in stale:
                del _last_emitted[jid]

    except Exception as e:
        logging.error(f"Progress poller error: {e}")


def _watchdog_check():
    """Check for zombie or dead PID jobs and mark them as failed."""
    try:
        with app.app_context():
            from arm.ripper.utils import watchdog_check
            watchdog_check()
    except Exception as e:
        logging.error(f"Watchdog check error: {e}")


def start_progress_poller(interval=2, watchdog_interval=60):
    """Start the background progress poller and watchdog."""
    import time

    def _loop():
        watchdog_counter = 0
        while True:
            socketio.sleep(interval)
            _check_active_jobs()
            watchdog_counter += interval
            if watchdog_counter >= watchdog_interval:
                watchdog_counter = 0
                _watchdog_check()

    socketio.start_background_task(_loop)


@socketio.on('connect', namespace='/ws/jobs')
def handle_connect():
    """Handle client connection to jobs namespace"""
    print('Client connected to /ws/jobs')


@socketio.on('disconnect', namespace='/ws/jobs')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected from /ws/jobs')


@socketio.on('subscribe_job', namespace='/ws/jobs')
def handle_subscribe_job(data):
    """Subscribe to updates for a specific job"""
    job_id = data.get('job_id')
    if job_id:
        join_room(f'job_{job_id}')
        emit('subscribed', {'job_id': job_id})


@socketio.on('unsubscribe_job', namespace='/ws/jobs')
def handle_unsubscribe_job(data):
    """Unsubscribe from updates for a specific job"""
    job_id = data.get('job_id')
    if job_id:
        leave_room(f'job_{job_id}')
        emit('unsubscribed', {'job_id': job_id})


@socketio.on('subscribe_all_jobs', namespace='/ws/jobs')
def handle_subscribe_all_jobs():
    """Subscribe to updates for all jobs"""
    join_room('all_jobs')
    emit('subscribed', {'type': 'all_jobs'})


@socketio.on('unsubscribe_all_jobs', namespace='/ws/jobs')
def handle_unsubscribe_all_jobs():
    """Unsubscribe from all jobs"""
    leave_room('all_jobs')
    emit('unsubscribed', {'type': 'all_jobs'})
