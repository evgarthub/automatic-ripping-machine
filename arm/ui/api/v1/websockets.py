"""
WebSocket handlers for real-time updates
"""
from flask_socketio import emit, join_room, leave_room
from arm.ui import socketio
import arm.config.config as cfg
from arm.models.job import Job
from arm.ui.json_api import process_logfile
import os


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
    """Unsubscribe from updates for all jobs"""
    leave_room('all_jobs')
    emit('unsubscribed', {'type': 'all_jobs'})


def emit_job_progress(job_id, progress_data):
    """Emit job progress update to subscribed clients"""
    room = f'job_{job_id}'
    socketio.emit('job_progress', {
        'job_id': job_id,
        'progress': progress_data
    }, to=room, namespace='/ws/jobs')

    # Also emit to all_jobs room
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

    # Also emit to all_jobs room
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

    # Also emit to all_jobs room
    socketio.emit('job_completed', {
        'job_id': job_id,
        'success': success,
        'message': message
    }, to='all_jobs', namespace='/ws/jobs')


# Function to be called from job processing code to send updates
def send_job_update(job_id):
    """Send job update to WebSocket clients"""
    try:
        job = Job.query.get(job_id)
        if not job:
            return

        # Get progress data
        progress_data = {
            'job_id': job.job_id,
            'status': job.status,
            'stage': getattr(job, 'stage', 'Unknown'),
            'progress': getattr(job, 'progress', '0'),
            'eta': getattr(job, 'eta', 'Unknown')
        }

        # Update progress if job is active
        if not job.finished:
            job_log = os.path.join(cfg.arm_config['LOGPATH'], str(job.logfile))
            process_logfile(job_log, job, progress_data)

        emit_job_progress(job_id, progress_data)

    except Exception as e:
        print(f"Error sending job update: {e}")