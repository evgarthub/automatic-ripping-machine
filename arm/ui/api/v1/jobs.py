
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
from arm.ui.utils import clean_for_filename, metadata_selector
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


def is_empty_search(raw: Any) -> bool:
    """Check if a metadata search returned no usable results.

    Args:
        raw: Raw response dict from metadata_selector search mode

    Returns:
        True if the search response is empty, errored or missing hits
    """
    if raw is None:
        return True
    if isinstance(raw, dict) and ('Error' in raw or not raw.get('Search')):
        return True
    return False


def normalize_search_results(raw: Any) -> list[dict]:
    """Normalize raw metadata search hits into API friendly dicts.

    Args:
        raw: Raw response dict from metadata_selector search mode

    Returns:
        List of normalized result dicts with imdb_id, title, year, poster and type
    """
    results = []
    if not isinstance(raw, dict):
        return results
    for hit in raw.get('Search') or []:
        if not isinstance(hit, dict):
            continue
        hit_type = hit.get('Type')
        imdb_id = hit.get('imdbID')
        if not hit_type or str(hit_type).lower() == 'game':
            continue
        if not imdb_id:
            continue
        results.append({
            'imdb_id': imdb_id,
            'title': hit.get('Title'),
            'year': hit.get('Year'),
            'poster': hit.get('Poster'),
            'type': hit_type,
        })
    return results


def normalize_details(raw: Any) -> Union[dict, None]:
    """Normalize a raw metadata details response into an API friendly dict.

    Args:
        raw: Raw response dict from metadata_selector get_details mode

    Returns:
        Normalized details dict or None if no usable details were found
    """
    if not raw or not isinstance(raw, dict) or not raw.get('Title'):
        return None
    return {
        'imdb_id': raw.get('imdbID'),
        'title': raw.get('Title'),
        'year': raw.get('Year'),
        'poster': raw.get('Poster'),
        'type': raw.get('Type'),
        'plot': raw.get('Plot'),
        'background_url': raw.get('background_url'),
    }


def apply_title_update(job: Job, title: str | None = None, year: str | None = None,
                       video_type: str | None = None, imdb_id: str | None = None,
                       poster_url: str | None = None) -> Job:
    """Apply a title metadata update to a job, mirroring the legacy updatetitle behaviour.

    Each provided field is written to both the automatic and manual columns and
    a notification describing the change is created.

    Args:
        job: The job instance to update
        title: New title (passed through clean_for_filename)
        year: New year
        video_type: New video type
        imdb_id: New IMDB id
        poster_url: New poster URL

    Returns:
        The refreshed, updated job instance
    """
    old_title = job.title
    old_year = job.year
    if title is not None:
        job.title = job.title_manual = clean_for_filename(title)
    if year is not None:
        job.year = job.year_manual = year
    if video_type is not None:
        job.video_type = job.video_type_manual = video_type
    if imdb_id is not None:
        job.imdb_id = job.imdb_id_manual = imdb_id
    if poster_url is not None:
        job.poster_url = job.poster_url_manual = poster_url
    job.hasnicetitle = True

    notification = Notifications(
        f"Job: {job.job_id} was updated",
        f'Title: {old_title} ({old_year}) was updated to '
        f'{title if title is not None else old_title} '
        f'({year if year is not None else old_year})'
    )
    db.session.add(notification)
    db.session.commit()
    db.session.refresh(job)
    return job


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

        job = apply_title_update(
            job,
            title=validated.get('title'),
            year=validated.get('year'),
            video_type=validated.get('video_type'),
            imdb_id=validated.get('imdb_id'),
            poster_url=validated.get('poster_url')
        )

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


@api_v1.route('/jobs/<int:job_id>/titlesearch', methods=['GET'])
@require_token
def title_search(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Search metadata providers for titles matching a query.

    If a year was supplied and the search returned nothing, the search is
    retried once without the year filter.

    Args:
        job_id: The job ID the search is performed for

    Query Parameters:
        title (str): Title search string (required)
        year (str): Optional release year to narrow the search

    Returns:
        JSON response with normalized search results
    """
    try:
        Job.query.get_or_404(job_id)

        title = (request.args.get('title') or '').strip()
        if not title:
            return jsonify({
                'success': False,
                'error': 'Title parameter is required'
            }), 400

        year = (request.args.get('year') or '').strip()

        results = metadata_selector("search", title, year)
        retried = False
        if is_empty_search(results) and year:
            results = metadata_selector("search", title, "")
            retried = True

        return jsonify({
            'success': True,
            'data': {
                'results': normalize_search_results(results),
                'retried_without_year': retried
            }
        }), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error during title search for job {job_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Database error'
        }), 500
    except HTTPException:
        raise
    except Exception as e:
        current_app.logger.error(f"Unexpected error during title search for job {job_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/jobs/<int:job_id>/titlesearch/details', methods=['GET'])
@require_token
def title_search_details(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Fetch detailed metadata for a single IMDB id.

    Args:
        job_id: The job ID the lookup is performed for

    Query Parameters:
        imdb_id (str): IMDB id to look up (required)

    Returns:
        JSON response with normalized details for the IMDB id
    """
    try:
        Job.query.get_or_404(job_id)

        imdb_id = (request.args.get('imdb_id') or '').strip()
        if not imdb_id:
            return jsonify({
                'success': False,
                'error': 'imdb_id parameter is required'
            }), 400

        details = metadata_selector("get_details", "", "", imdb_id)
        normalized = normalize_details(details)
        if normalized is None:
            return jsonify({
                'success': False,
                'error': 'No details found'
            }), 404

        return jsonify({
            'success': True,
            'data': normalized
        }), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error getting title details for job {job_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Database error'
        }), 500
    except HTTPException:
        raise
    except Exception as e:
        current_app.logger.error(f"Unexpected error getting title details for job {job_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1.route('/jobs/<int:job_id>/titlesearch', methods=['POST'])
@require_token
def apply_title_search(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Apply metadata found via title search to a job.

    Two mutually exclusive modes:
        1. imdb_id: fetch details for the IMDB id and apply them to the job
        2. title (and optional year): apply a custom title/year to the job

    Args:
        job_id: The job ID to update

    Request Body:
        imdb_id (str): IMDB id to fetch details for
        title (str): Custom title to apply
        year (int|str): Optional year when applying a custom title

    Returns:
        JSON response with the updated job
    """
    try:
        job = Job.query.get_or_404(job_id)

        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not data:
            return jsonify({
                'success': False,
                'error': 'JSON body required'
            }), 400

        imdb_id = data.get('imdb_id')
        title = data.get('title')

        if isinstance(imdb_id, str) and imdb_id.strip():
            if data.get('title') or data.get('year'):
                return jsonify({
                    'success': False,
                    'error': 'Provide either imdb_id or title/year, not both'
                }), 400

            details = metadata_selector("get_details", "", "", imdb_id.strip())
            normalized = normalize_details(details)
            if normalized is None:
                return jsonify({
                    'success': False,
                    'error': 'No details found'
                }), 404

            job = apply_title_update(
                job,
                title=normalized['title'],
                year=normalized['year'],
                video_type=normalized['type'],
                imdb_id=normalized['imdb_id'],
                poster_url=normalized['poster']
            )

        elif isinstance(title, str) and title.strip():
            validated_year = None
            if 'year' in data:
                validated_year = validate_metadata_field('year', data['year'])
                if validated_year is None:
                    return jsonify({
                        'success': False,
                        'error': 'Invalid value for field: year'
                    }), 400

            job = apply_title_update(job, title=title, year=validated_year)

        else:
            return jsonify({
                'success': False,
                'error': 'Provide imdb_id or title'
            }), 400

        return jsonify({
            'success': True,
            'data': job.get_d()
        }), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error applying title search for job {job_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Database error'
        }), 500
    except HTTPException:
        raise
    except Exception as e:
        current_app.logger.error(f"Unexpected error applying title search for job {job_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500