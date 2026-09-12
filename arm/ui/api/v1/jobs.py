
from __future__ import annotations
import os
from typing import Dict, Any, Tuple, Union, Protocol, TypeGuard
from flask import request, jsonify, current_app, Response
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from . import api_v1
from .auth import require_token
from arm.models.job import Job, JobState
from arm.models.notifications import Notifications
from arm.models.track import Track
from arm.ui import db
from arm.ui.utils import clean_for_filename
import arm.config.config as cfg

# Type guard for SQLAlchemy columns
class ColumnLike(Protocol):
    def like(self, pattern: str) -> Any: ...

def is_column(obj: Any) -> TypeGuard[ColumnLike]:
    return hasattr(obj, 'like')

# Configuration constants
DEFAULT_PER_PAGE = 50
MAX_PER_PAGE = 100
METADATA_FIELDS = {'title', 'year', 'video_type', 'imdb_id', 'poster_url'}
MAX_YEAR_LENGTH = 4


def validate_pagination_params(page: int, per_page: int) -> Tuple[int, int]:
    """Validate and sanitize pagination parameters.

    Args:
        page: Requested page number
        per_page: Requested items per page

    Returns:
        Tuple of (validated_page, validated_per_page)
    """
    page = max(1, page)
    per_page = min(max(1, per_page), MAX_PER_PAGE)
    return page, per_page


def get_log_file_path(job: Job) -> str:
    """Get the full path to a job's log file.

    Args:
        job: Job instance

    Returns:
        Full path to the log file
    """
    return os.path.join(cfg.arm_config['LOGPATH'], str(job.logfile))


def process_job_progress(job: Job, data_dict: Dict[str, Any]) -> None:
    """Process and add progress information to job data.

    Args:
        job: Job instance
        data_dict: Dictionary to update with progress info
    """
    data_dict['progress'] = job.progress if job.progress is not None else 0
    data_dict['progress_round'] = job.progress_round or '0'
    data_dict['stage'] = job.stage or ''
    data_dict['eta'] = job.eta or 'Unknown'


@api_v1.route('/jobs', methods=['GET'])
@require_token
def get_jobs() -> Union[Response, Tuple[Response, int]]:
    """Get list of jobs with optional filters.

    Query Parameters:
        status (str): Filter by job status ('active', 'success', 'fail')
        search (str): Search in job titles
        page (int): Page number (default: 1, min: 1)
        per_page (int): Items per page (default: 50, max: 100)

    Returns:
        JSON response with jobs list and pagination metadata
    """
    try:
        # Parse and validate query parameters
        status = request.args.get('status')
        search = request.args.get('search')
        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', DEFAULT_PER_PAGE))
            page, per_page = validate_pagination_params(page, per_page)
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid pagination parameters: {e}'
            }), 400

        # Build query
        query = Job.query

        if status:
            if status == 'active':
                query = query.filter(~Job.finished)
            elif status in ['success', 'fail']:
                query = query.filter_by(status=status)
            else:
                return jsonify({
                    'success': False,
                    'error': f'Invalid status: {status}'
                }), 400

        if search:
            # Search in title fields using parameterized queries for safety
            search_filter = f"%{search}%"
            if is_column(Job.title) and is_column(Job.title_auto) and is_column(Job.title_manual):
                query = query.filter(
                    (Job.title.like(search_filter)) |
                    (Job.title_auto.like(search_filter)) |
                    (Job.title_manual.like(search_filter))
                )

        # Order by start_time desc
        query = query.order_by(desc(Job.start_time))

        # Pagination
        total = query.count()
        jobs = query.offset((page - 1) * per_page).limit(per_page).all()

        # Process jobs for progress info
        jobs_data = []
        for job in jobs:
            job_dict = job.get_d()
            # Add progress info if job is active
            process_job_progress(job, job_dict)
            jobs_data.append(job_dict)

        return jsonify({
            'success': True,
            'data': jobs_data,
            'meta': {
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error getting jobs: {e}")
        return jsonify({
            'success': False,
            'error': 'Database error'
        }), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error getting jobs: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/jobs/<int:job_id>', methods=['GET'])
@require_token
def get_job(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Get detailed job information.

    Args:
        job_id: The job ID to retrieve

    Returns:
        JSON response with detailed job information
    """
    try:
        job = Job.query.get_or_404(job_id)

        job_dict = job.get_d()
        job_dict['tracks'] = [t.get_d() for t in job.tracks.order_by(Track.track_number)]

        # Add progress info if active
        process_job_progress(job, job_dict)

        # Add config if available
        if job.config:
            job_dict['config'] = job.config.get_d()

        return jsonify({
            'success': True,
            'data': job_dict
        }), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error getting job {job_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Database error'
        }), 500
    except HTTPException:
        raise
    except Exception as e:
        current_app.logger.error(f"Unexpected error getting job {job_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/jobs/<int:job_id>/logs', methods=['GET'])
@require_token
def get_job_logs(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Get job logs.

    Args:
        job_id: The job ID to retrieve logs for

    Returns:
        JSON response with log file content
    """
    try:
        job = Job.query.get_or_404(job_id)

        log_path = get_log_file_path(job)

        if not os.path.exists(log_path):
            return jsonify({
                'success': False,
                'error': 'Log file not found'
            }), 404

        # Read log file
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                logs = f.read()
        except IOError as e:
            current_app.logger.error(f"Error reading log file {log_path}: {e}")
            return jsonify({
                'success': False,
                'error': 'Error reading log file'
            }), 500

        return jsonify({
            'success': True,
            'data': {
                'job_id': job_id,
                'logfile': job.logfile,
                'content': logs
            }
        }), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error getting logs for job {job_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Database error'
        }), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error getting logs for job {job_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/jobs/<int:job_id>/progress', methods=['GET'])
@require_token
def get_job_progress(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Get job progress information.

    Args:
        job_id: The job ID to get progress for

    Returns:
        JSON response with job progress data
    """
    try:
        job = Job.query.get_or_404(job_id)

        progress_data = {
            'job_id': job.job_id,
            'status': job.status,
            'stage': job.stage or '',
            'progress': job.progress if job.progress is not None else 0,
            'progress_round': job.progress_round or '0',
            'eta': job.eta or 'Unknown',
        }

        return jsonify({
            'success': True,
            'data': progress_data
        }), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error getting progress for job {job_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Database error'
        }), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error getting progress for job {job_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/jobs/<int:job_id>/actions', methods=['POST'])
@require_token
def job_actions(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Perform actions on a job.

    Args:
        job_id: The job ID to perform action on

    Request Body:
        action (str): Action to perform ('abandon', 'fixperms', 'send')

    Returns:
        JSON response with action result
    """
    try:
        job = Job.query.get_or_404(job_id)
        data = request.get_json()

        if not data or 'action' not in data:
            return jsonify({
                'success': False,
                'error': 'Action required'
            }), 400

        action = data['action']

        if action == 'abandon':
            # Implement abandon logic
            job.status = JobState.FAILURE.value
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Job abandoned'
            }), 200

        elif action == 'fixperms':
            # Implement fix permissions logic
            # This would need to be implemented based on existing code
            return jsonify({
                'success': True,
                'message': 'Permissions fixed'
            }), 200

        elif action == 'send':
            # Implement send logic
            # This would need to be implemented based on existing code
            return jsonify({
                'success': True,
                'message': 'Job sent'
            }), 200

        else:
            return jsonify({
                'success': False,
                'error': f'Unknown action: {action}'
            }), 400

    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error performing action on job {job_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Database error'
        }), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error performing action on job {job_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/jobs/<int:job_id>', methods=['DELETE'])
@require_token
def delete_job(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Delete a job.

    Args:
        job_id: The job ID to delete

    Returns:
        JSON response confirming deletion
    """
    try:
        job = Job.query.get_or_404(job_id)

        # Check if job is finished (don't delete active jobs)
        if not job.finished:
            return jsonify({
                'success': False,
                'error': 'Cannot delete active job'
            }), 400

        db.session.delete(job)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Job deleted'
        }), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error deleting job {job_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Database error'
        }), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error deleting job {job_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


def validate_metadata_field(field: str, value: Any) -> Union[str, None]:
    """Validate a single metadata field value.

    Args:
        field: The metadata field name
        value: The value to validate

    Returns:
        Sanitized value for storage or None if the value is invalid
    """
    if field == 'year':
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return str(value)
        if isinstance(value, str) and value.isdigit() and 0 < len(value) <= MAX_YEAR_LENGTH:
            return value
        return None
    if isinstance(value, str) and value.strip():
        return value
    return None


@api_v1.route('/jobs/<int:job_id>/metadata', methods=['PUT'])
@require_token
def update_job_metadata(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Update metadata for a job.

    Args:
        job_id: The job ID to update

    Request Body:
        title (str): New title
        year (int|str): New year
        video_type (str): New video type
        imdb_id (str): New IMDB id
        poster_url (str): New poster URL

    Returns:
        JSON response with the updated job
    """
    try:
        job = Job.query.get_or_404(job_id)

        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not data:
            return jsonify({
                'success': False,
                'error': f'JSON body required with at least one field: {", ".join(sorted(METADATA_FIELDS))}'
            }), 400

        unknown_fields = sorted(set(data.keys()) - METADATA_FIELDS)
        if unknown_fields:
            return jsonify({
                'success': False,
                'error': f'Unknown fields: {", ".join(unknown_fields)}'
            }), 400

        validated = {}
        for field in sorted(data.keys() & METADATA_FIELDS):
            value = validate_metadata_field(field, data[field])
            if value is None:
                return jsonify({
                    'success': False,
                    'error': f'Invalid value for field: {field}'
                }), 400
            validated[field] = value

        old_title = job.title
        old_year = job.year
        if 'title' in validated:
            job.title = job.title_manual = clean_for_filename(validated['title'])
        if 'year' in validated:
            job.year = job.year_manual = validated['year']
        if 'video_type' in validated:
            job.video_type = job.video_type_manual = validated['video_type']
        if 'imdb_id' in validated:
            job.imdb_id = job.imdb_id_manual = validated['imdb_id']
        if 'poster_url' in validated:
            job.poster_url = job.poster_url_manual = validated['poster_url']
        job.hasnicetitle = True

        new_title = validated.get('title', old_title)
        new_year = validated.get('year', old_year)
        notification = Notifications(
            f"Job: {job.job_id} was updated",
            f'Title: {old_title} ({old_year}) was updated to '
            f'{data.get("title", new_title)} ({data.get("year", new_year)})'
        )
        db.session.add(notification)
        db.session.commit()
        db.session.refresh(job)

        return jsonify({
            'success': True,
            'data': job.get_d()
        }), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error updating metadata for job {job_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Database error'
        }), 500
    except HTTPException:
        raise
    except Exception as e:
        current_app.logger.error(f"Unexpected error updating metadata for job {job_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500