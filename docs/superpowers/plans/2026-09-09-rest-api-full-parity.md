# REST API Full Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the `/api/v1` REST API so the `arm-react` SPA can do everything the legacy Jinja2 UI does, with consistent JSON envelopes, bearer-token auth (hashed at rest), fixed bugs, and live WebSocket job updates.

**Architecture:** Extend the existing `arm/ui/api/v1/` Flask blueprint incrementally. New endpoint modules call the same helper functions the legacy routes use (`arm.ui.utils`, `arm.ui.json_api`, `DriveUtils`) — no duplicated business logic, legacy Jinja routes untouched. WebSocket updates come from a UI-process background watchdog that polls job state and emits diffs (the ripper runs as a separate process, so it cannot emit directly without a broker).

**Tech Stack:** Flask + Flask-SQLAlchemy + Flask-SocketIO (existing, pinned in `requirements.txt`; **no new runtime deps**). Tests: stdlib `unittest` style run by pytest.

## Global Constraints

- Python 3.9–3.12 compatible (CI matrix).
- flake8 clean: `max-line-length=160`, run `python3 -m flake8 arm test` (config in `setup.cfg`).
- Response envelope everywhere in `/api/v1`: success `{"success": true, "data": ..., "message"?: ..., "meta"?: ...}`; error `{"success": false, "error": {"code": str, "message": str}}` with proper HTTP status (400/401/403/404/405/409/500).
- Every `/api/v1` route requires `Authorization: Bearer <token>` except `POST /api/v1/auth/token`.
- No new dependencies in `requirements.txt`. Delete unused `arm/ui/api/v1/schemas.py` (imports unlisted `marshmallow`).
- Legacy Jinja UI must keep working unchanged (no edits to legacy route behavior).
- **Tests require POSIX** (`fcntl`, `pyudev` are imported transitively via `arm.models.system_drives`). On Windows run via WSL: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui -v"`. Ensure WSL python has `pip3 install -r requirements.txt pytest`. If WSL is unavailable, rely on CI after pushing the branch.
- Test harness boots the real `arm.ui` app (module-level `app`) using a generated throwaway `ARM_CONFIG_FILE`; per-test isolation via `db.drop_all()` + `db.create_all()` on that same file DB (never swap `SQLALCHEMY_DATABASE_URI` — Flask-SQLAlchemy caches engines).
- Commit after every task. Never commit `arm.db`/tmp artifacts (add `test/*.db` to `.gitignore` if needed).

## File Structure (final state)

```
arm/ui/api/v1/
├── __init__.py       # blueprint + error handlers (modify)
├── helpers.py        # NEW envelope/pagination helpers
├── auth.py           # token flow rewritten (hashed tokens)
├── jobs.py           # envelope retrofit + real actions + title/tracks/params
├── metadata.py       # NEW provider search/details
├── history.py        # NEW finished-job listing
├── logs.py           # NEW log listing/tail
├── settings_api.py   # NEW arm.yaml/UI/abcde/apprise settings
├── database.py       # NEW db browse/migrate/import
├── config.py         # envelope retrofit only
├── system.py         # drive serialization fix + drive actions
├── notifications.py  # timeout wiring + clear-all + envelope
├── websockets.py     # connect auth + job watchdog
└── schemas.py        # DELETED
arm/models/token.py   # SHA-256 hashed token storage
arm/ui/__init__.py    # csrf.exempt, SECRET_KEY env, CORS restrict
arm/runui.py          # start websocket watchdog
arm-react/vite.config.ts  # dev proxy to Flask
test/unittest/ui/api/     # NEW tests (base.py + per-module test files)
```

---

### Task 1: API test harness

**Files:**
- Create: `test/unittest/ui/__init__.py` (empty)
- Create: `test/unittest/ui/api/__init__.py` (empty)
- Create: `test/unittest/ui/api/base.py`
- Test: `test/unittest/ui/api/test_smoke.py`

**Interfaces:**
- Produces: pytest fixtures/functions used by all later tasks:
  - `base.ApiTestBase(unittest.TestCase)` with `.client`, `.create_admin(email, password) -> User`, `.get_token(email, password) -> str`, `.auth(token) -> dict`, `.make_job(**attrs) -> Job`, `.make_notification(title, message) -> Notifications`
  - `base.REPO_ROOT` (absolute repo path)

- [ ] **Step 1: Write the harness**

`test/unittest/ui/api/base.py`:

```python
"""Shared harness for API v1 tests.

Boots the real ARM Flask app against a throwaway config + sqlite DB so the
blueprints under test behave exactly as in production. Requires POSIX
(fcntl/pyudev) - run under WSL/Linux/CI on Windows machines.
"""
import os
import sys
import tempfile
import unittest

import bcrypt

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

_BOOTSTRAPPED = False


def _write_test_config(tmp_dir):
    """Create a minimal arm.yaml pointing at tmp paths; returns its path."""
    config_path = os.path.join(tmp_dir, 'arm.yaml')
    with open(config_path, 'w', encoding='utf-8') as fh:
        fh.write(
            f"INSTALLPATH: {REPO_ROOT}\n"
            f"DBFILE: {os.path.join(tmp_dir, 'arm.db')}\n"
            f"LOGPATH: {os.path.join(tmp_dir, 'logs')}\n"
            f"ABCDE_CONFIG_FILE: {os.path.join(tmp_dir, '.abcde.conf')}\n"
            f"APPRISE: {os.path.join(tmp_dir, 'apprise.yaml')}\n"
            "DISABLE_LOGIN: false\n"
        )
    os.makedirs(os.path.join(tmp_dir, 'logs'), exist_ok=True)
    with open(os.path.join(tmp_dir, '.abcde.conf'), 'w', encoding='utf-8') as fh:
        fh.write('# abcde test config\n')
    return config_path


def _bootstrap():
    """Import arm.ui exactly once with the throwaway config in place."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    tmp_dir = tempfile.mkdtemp(prefix='arm_api_test_')
    os.environ['ARM_CONFIG_FILE'] = _write_test_config(tmp_dir)
    import arm.ui  # noqa: F401  pylint: disable=unused-import
    _BOOTSTRAPPED = True


class ApiTestBase(unittest.TestCase):
    """Base class: clean DB per test, token helpers, JSON client."""

    @classmethod
    def setUpClass(cls):
        _bootstrap()
        from arm.ui import app as flask_app
        cls.app = flask_app
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def setUp(self):
        from arm.ui import db
        self.db = db
        with self.app.app_context():
            db.drop_all()
            db.create_all()
        self.client = self.app.test_client()

    # ---- helpers -------------------------------------------------------
    def create_admin(self, email='admin@example.com', password='password123'):
        from arm.models.user import User
        salt = bcrypt.gensalt()
        user = User(email=email,
                    password=bcrypt.hashpw(password.encode('utf-8'), salt),
                    hashed=salt)
        self.db.session.add(user)
        self.db.session.commit()
        return user

    def get_token(self, email='admin@example.com', password='password123'):
        resp = self.client.post('/api/v1/auth/token',
                                json={'username': email, 'password': password})
        assert resp.status_code == 201, resp.get_data(as_text=True)
        return resp.get_json()['data']['token']

    def auth(self, token):
        return {'Authorization': f'Bearer {token}'}

    def make_job(self, **attrs):
        """Create a Job row without running __init__ (no udev/psutil)."""
        from arm.models.job import Job
        job = Job.__new__(Job)
        defaults = {'status': 'success', 'title': 'Test Movie', 'title_auto': 'Test Movie',
                    'title_manual': None, 'year': '2020', 'year_auto': '2020',
                    'year_manual': None, 'video_type': 'movie', 'disctype': 'dvd',
                    'hasnicetitle': True, 'logfile': 'test_movie.log', 'ejected': False,
                    'updated': False, 'manual_start': False, 'manual_mode': False,
                    'progress': None, 'stage': None, 'start_time': None, 'stop_time': None,
                    'path': None, 'pid': None, 'pid_hash': None, 'devpath': '/dev/sr0',
                    'no_of_titles': 1, 'label': 'TESTMOVIE', 'crc_id': None,
                    'imdb_id': None, 'imdb_id_auto': None, 'imdb_id_manual': None,
                    'poster_url': None, 'poster_url_auto': None, 'poster_url_manual': None,
                    'video_type_auto': None, 'video_type_manual': None,
                    'mountpoint': '', 'errors': None, 'is_iso': False, 'job_length': None,
                    'arm_version': None}
        defaults.update(attrs)
        for key, value in defaults.items():
            setattr(job, key, value)
        self.db.session.add(job)
        self.db.session.commit()
        return job

    def make_notification(self, title='note', message='msg'):
        from arm.models.notifications import Notifications
        note = Notifications(title=title, message=message)
        self.db.session.add(note)
        self.db.session.commit()
        return note
```

- [ ] **Step 2: Write the smoke test**

`test/unittest/ui/api/test_smoke.py`:

```python
"""Smoke tests: harness works, API requires auth."""
from test.unittest.ui.api.base import ApiTestBase


class TestApiSmoke(ApiTestBase):

    def test_jobs_requires_token(self):
        resp = self.client.get('/api/v1/jobs')
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(resp.get_json()['success'])

    def test_token_flow_and_authed_request(self):
        self.create_admin()
        token = self.get_token()
        resp = self.client.get('/api/v1/jobs', headers=self.auth(token))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['success'])

    def test_bad_credentials_rejected(self):
        self.create_admin()
        resp = self.client.post('/api/v1/auth/token',
                                json={'username': 'admin@example.com',
                                      'password': 'wrong'})
        self.assertEqual(resp.status_code, 401)
```

- [ ] **Step 3: Run tests (harness verification)**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui -v"`
Expected: 3 passed. (First run is slow: config bootstrap runs alembic on the tmp DB.) If WSL/python deps missing: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && pip3 install -r requirements.txt pytest"` first.

- [ ] **Step 4: Commit**

```bash
git add test/unittest/ui
git commit -m "test(api): add API v1 test harness booting real Flask app"
```

---

### Task 2: Response helpers, JSON error handlers, retrofit existing endpoints

**Files:**
- Create: `arm/ui/api/v1/helpers.py`
- Modify: `arm/ui/api/v1/__init__.py`
- Modify: `arm/ui/api/v1/jobs.py` (envelopes; keep stub actions until Task 4)
- Modify: `arm/ui/api/v1/config.py`, `arm/ui/api/v1/system.py` (GET routes only here), `arm/ui/api/v1/notifications.py` (existing routes only here)
- Test: `test/unittest/ui/api/test_helpers.py`

**Interfaces:**
- Produces (used by all later tasks):
  - `helpers.api_success(data=None, message=None, meta=None, status=200) -> (Response, int)`
  - `helpers.api_error(message, status=400, code='error') -> (Response, int)`
  - `helpers.parse_pagination() -> Tuple[int, int] | None` (page, per_page clamped 1..100)
  - `helpers.pagination_meta(total, page, per_page) -> dict`
  - `helpers.register_error_handlers(blueprint)` (JSON for 404/405/500 inside the blueprint)

- [ ] **Step 1: Write failing tests**

`test/unittest/ui/api/test_helpers.py`:

```python
"""Envelope + error-handler tests."""
from test.unittest.ui.api.base import ApiTestBase


class TestEnvelope(ApiTestBase):

    def test_unknown_job_returns_json_404(self):
        token = self.get_token() if self.create_admin() else None
        resp = self.client.get('/api/v1/jobs/9999', headers=self.auth(token))
        self.assertEqual(resp.status_code, 404)
        body = resp.get_json()
        self.assertFalse(body['success'])
        self.assertIn('code', body['error'])
        self.assertIn('message', body['error'])

    def test_method_not_allowed_returns_json_405(self):
        self.create_admin()
        token = self.get_token()
        resp = self.client.delete('/api/v1/jobs', headers=self.auth(token))
        self.assertEqual(resp.status_code, 405)
        self.assertFalse(resp.get_json()['success'])

    def test_jobs_list_envelope(self):
        self.create_admin()
        self.make_job()
        token = self.get_token()
        resp = self.client.get('/api/v1/jobs', headers=self.auth(token))
        body = resp.get_json()
        self.assertTrue(body['success'])
        self.assertEqual(len(body['data']), 1)
        self.assertEqual(body['meta']['total'], 1)

    def test_bad_pagination_returns_json_400(self):
        self.create_admin()
        token = self.get_token()
        resp = self.client.get('/api/v1/jobs?page=abc', headers=self.auth(token))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()['success'])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui/api/test_helpers.py -v"`
Expected: FAIL (404 returns HTML from `get_or_404`; envelope shapes differ).

- [ ] **Step 3: Implement helpers + error handlers**

`arm/ui/api/v1/helpers.py`:

```python
"""Shared helpers for API v1: envelopes, pagination, JSON error handling."""
from flask import jsonify, request


def api_success(data=None, message=None, meta=None, status=200):
    """Build a success envelope. Omits keys that were not provided."""
    payload = {'success': True}
    if data is not None:
        payload['data'] = data
    if message is not None:
        payload['message'] = message
    if meta is not None:
        payload['meta'] = meta
    return jsonify(payload), status


def api_error(message, status=400, code='error'):
    """Build an error envelope: {"success": false, "error": {code, message}}."""
    return jsonify({'success': False,
                    'error': {'code': code, 'message': message}}), status


def parse_pagination():
    """Read page/per_page query params, clamped to sane bounds.

    Returns (page, per_page) or None when the params are not integers.
    """
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(max(1, int(request.args.get('per_page', 50))), 100)
    except (TypeError, ValueError):
        return None
    return page, per_page


def pagination_meta(total, page, per_page):
    """Standard pagination metadata block."""
    return {
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
    }


def register_error_handlers(blueprint):
    """Return JSON (not Flask HTML pages) for common HTTP errors in the blueprint."""
    @blueprint.errorhandler(404)
    def not_found(_error):
        return api_error('Not found', 404, 'not_found')

    @blueprint.errorhandler(405)
    def method_not_allowed(_error):
        return api_error('Method not allowed', 405, 'method_not_allowed')

    @blueprint.errorhandler(500)
    def server_error(_error):
        return api_error('Internal server error', 500, 'internal_error')
```

`arm/ui/api/v1/__init__.py` (full replacement):

```python
"""
ARM REST API v1 Blueprint
Provides modern RESTful endpoints for external applications
"""
from flask import Blueprint

api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

from .helpers import register_error_handlers  # noqa: E402
register_error_handlers(api_v1)

from . import auth, jobs, config, system, notifications, websockets  # noqa: E402,F401
```

- [ ] **Step 4: Retrofit `jobs.py` responses**

Replace every ad-hoc `jsonify({...}), code` in `arm/ui/api/v1/jobs.py` with helper calls and replace `Job.query.get_or_404(job_id)` with manual lookups. Full new file content (actions `fixperms`/`send` remain stubs until Task 4):

```python
"""API v1 job routes."""
from __future__ import annotations

import os
from typing import Any, Dict, Tuple, Union

from flask import current_app, request, Response
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError

from arm.models.job import Job
from arm.ui import db
from arm.ui.json_api import process_logfile
import arm.config.config as cfg

from . import api_v1
from .auth import require_token
from .helpers import api_error, api_success, pagination_meta, parse_pagination

DEFAULT_PER_PAGE = 50


def get_log_file_path(job: Job) -> str:
    """Full path to a job's log file."""
    return os.path.join(cfg.arm_config['LOGPATH'], str(job.logfile))


def process_job_progress(job: Job, data_dict: Dict[str, Any]) -> None:
    """Add parsed progress info for unfinished jobs."""
    if not job.finished:
        process_logfile(get_log_file_path(job), job, data_dict)


def get_job_or_404(job_id: int):
    """Fetch a Job or return the standard JSON 404 envelope."""
    job = Job.query.get(job_id)
    if job is None:
        return None, api_error(f'Job {job_id} not found', 404, 'not_found')
    return job, None


@api_v1.route('/jobs', methods=['GET'])
@require_token
def get_jobs() -> Union[Response, Tuple[Response, int]]:
    """List jobs with optional status/search filters and pagination."""
    try:
        pagination = parse_pagination()
        if pagination is None:
            return api_error('Invalid pagination parameters', 400, 'validation_error')
        page, per_page = pagination

        status = request.args.get('status')
        search = request.args.get('search')

        query = Job.query
        if status:
            if status == 'active':
                query = query.filter(~Job.finished)
            elif status in ('success', 'fail'):
                query = query.filter_by(status=status)
            else:
                return api_error(f'Invalid status: {status}', 400, 'validation_error')

        if search:
            pattern = f"%{search}%"
            query = query.filter((Job.title.like(pattern))
                                 | (Job.title_auto.like(pattern))
                                 | (Job.title_manual.like(pattern)))

        query = query.order_by(desc(Job.start_time), desc(Job.job_id))
        total = query.count()
        jobs = query.offset((page - 1) * per_page).limit(per_page).all()

        jobs_data = []
        for job in jobs:
            job_dict = job.get_d()
            process_job_progress(job, job_dict)
            jobs_data.append(job_dict)

        return api_success(data=jobs_data, meta=pagination_meta(total, page, per_page))

    except SQLAlchemyError as err:
        current_app.logger.error(f'Database error getting jobs: {err}')
        return api_error('Database error', 500, 'database_error')


@api_v1.route('/jobs/<int:job_id>', methods=['GET'])
@require_token
def get_job(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Detailed job information including per-job config."""
    try:
        job, error = get_job_or_404(job_id)
        if error:
            return error
        job_dict = job.get_d()
        process_job_progress(job, job_dict)
        if job.config:
            job_dict['config'] = job.config.get_d()
        return api_success(data=job_dict)
    except SQLAlchemyError as err:
        current_app.logger.error(f'Database error getting job {job_id}: {err}')
        return api_error('Database error', 500, 'database_error')


@api_v1.route('/jobs/<int:job_id>/logs', methods=['GET'])
@require_token
def get_job_logs(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Full content of the job's log file."""
    try:
        job, error = get_job_or_404(job_id)
        if error:
            return error
        log_path = get_log_file_path(job)
        if not os.path.exists(log_path):
            return api_error('Log file not found', 404, 'not_found')
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as handle:
                logs = handle.read()
        except IOError as err:
            current_app.logger.error(f'Error reading log file {log_path}: {err}')
            return api_error('Error reading log file', 500, 'io_error')
        return api_success(data={'job_id': job_id, 'logfile': job.logfile, 'content': logs})
    except SQLAlchemyError as err:
        current_app.logger.error(f'Database error getting logs for job {job_id}: {err}')
        return api_error('Database error', 500, 'database_error')


@api_v1.route('/jobs/<int:job_id>/progress', methods=['GET'])
@require_token
def get_job_progress(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Current progress/stage/eta for a job."""
    try:
        job, error = get_job_or_404(job_id)
        if error:
            return error
        progress_data = {
            'job_id': job.job_id,
            'status': job.status,
            'stage': getattr(job, 'stage', 'Unknown'),
            'progress': getattr(job, 'progress', '0'),
            'eta': getattr(job, 'eta', 'Unknown'),
        }
        process_job_progress(job, progress_data)
        return api_success(data=progress_data)
    except SQLAlchemyError as err:
        current_app.logger.error(f'Database error getting progress for job {job_id}: {err}')
        return api_error('Database error', 500, 'database_error')


@api_v1.route('/jobs/<int:job_id>/actions', methods=['POST'])
@require_token
def job_actions(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Perform an action on a job: abandon | fixperms | send."""
    try:
        job, error = get_job_or_404(job_id)
        if error:
            return error
        data = request.get_json(silent=True) or {}
        action = data.get('action')
        if not action:
            return api_error('action is required', 400, 'validation_error')

        if action == 'abandon':
            from arm.ui.json_api import terminate_process
            try:
                terminate_process(job.pid)
            except ValueError as err:
                db.session.rollback()
                return api_error(str(err), 500, 'abandon_error')
            job.status = 'fail'
            job.eject()
            db.session.commit()
            return api_success(message=f'Job {job_id} abandoned')

        if action == 'fixperms':
            return api_success(message='Permissions fixed')  # stub until Task 4

        if action == 'send':
            return api_success(message='Job sent')  # stub until Task 4

        return api_error(f'Unknown action: {action}', 400, 'validation_error')

    except SQLAlchemyError as err:
        current_app.logger.error(f'Database error performing action on job {job_id}: {err}')
        db.session.rollback()
        return api_error('Database error', 500, 'database_error')


@api_v1.route('/jobs/<int:job_id>', methods=['DELETE'])
@require_token
def delete_job(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Delete a finished job (and its tracks/config) from the database."""
    try:
        job, error = get_job_or_404(job_id)
        if error:
            return error
        if not job.finished:
            return api_error('Cannot delete active job', 409, 'job_active')
        from arm.models.track import Track
        from arm.models.config import Config
        from arm.ui.settings import DriveUtils
        Track.query.filter_by(job_id=job_id).delete()
        Config.query.filter_by(job_id=job_id).delete()
        DriveUtils.job_cleanup(job_id)
        db.session.delete(job)
        db.session.commit()
        return api_success(message=f'Job {job_id} deleted')
    except SQLAlchemyError as err:
        current_app.logger.error(f'Database error deleting job {job_id}: {err}')
        db.session.rollback()
        return api_error('Database error', 500, 'database_error')
```

Note: this intentionally uses raw `'fail'`/`'success'` strings — they equal `JobState.FAILURE.value`/`JobState.SUCCESS.value` and avoid enum churn.

- [ ] **Step 5: Retrofit `config.py`, `system.py` GET routes, `notifications.py` existing routes**

For each file: import helpers (`from .helpers import api_success, api_error`) and mechanically replace every `jsonify({...}), code` response with `api_success(...)`/`api_error(...)`. Specifics:

- `config.py`: `get_config` 404 → `api_error('Configuration not found', 404, 'not_found')`; success → `api_success(data=config.get_d())`. `update_config`: 400 no data → `api_error('No data provided', 400, 'validation_error')`; 404 same; success → `api_success(message='Configuration updated')`; empty update → `api_error('No valid fields to update', 400, 'validation_error')`; 500s → `api_error('Internal server error', 500, 'internal_error')`.
- `system.py`: all five routes keep their logic; replace only response construction (`api_success(data=info)` etc., errors via `api_error(..., 500, 'internal_error')`). **Do not touch `get_drives` serialization yet** — that is Task 9 (it is currently broken and gets fixed there).
- `notifications.py`: `get_notifications` → `api_success(data=result, meta=pagination_meta(total, page, per_page))` (add `from .helpers import ...`); `mark_notification_read` → manual lookup instead of `get_or_404`, 404 envelope, success `api_success(message=...)`.

- [ ] **Step 6: Run tests**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui -v"`
Expected: all pass (smoke + helpers).

- [ ] **Step 7: Commit**

```bash
git add arm/ui/api/v1 test/unittest/ui
git commit -m "refactor(api): consistent JSON envelope + error handlers for v1"
```

---

### Task 3: Security fixes — CSRF exempt, SECRET_KEY, CORS, hashed tokens, drop schemas.py

**Files:**
- Delete: `arm/ui/api/v1/schemas.py`
- Modify: `arm/ui/__init__.py`
- Modify: `arm/models/token.py` (full rewrite)
- Modify: `arm/ui/api/v1/auth.py` (full rewrite)
- Test: `test/unittest/ui/api/test_auth_security.py`

**Interfaces:**
- Produces:
  - `Token.issue(user_id, expiry_hours=24) -> Tuple[str, Token]` — returns `(raw_token, token_row)`; raw token is shown once, DB stores `sha256(raw)`.
  - `Token.validate_token(raw_token) -> User | None`, `Token.revoke_token(raw_token) -> bool` (both accept the **raw** bearer token).
  - Breaking change: existing plaintext tokens are invalidated (feature branch, acceptable — note in README).

- [ ] **Step 1: Write failing tests**

`test/unittest/ui/api/test_auth_security.py`:

```python
"""Security: hashed tokens, CSRF exemption, SECRET_KEY."""
from test.unittest.ui.api.base import ApiTestBase


class TestTokenHashing(ApiTestBase):

    def test_token_is_hashed_at_rest(self):
        self.create_admin()
        resp = self.client.post('/api/v1/auth/token',
                                json={'username': 'admin@example.com',
                                      'password': 'password123'})
        self.assertEqual(resp.status_code, 201)
        raw = resp.get_json()['data']['token']

        from arm.models.token import Token
        row = Token.query.first()
        self.assertNotEqual(row.token_hash, raw)
        self.assertEqual(len(row.token_hash), 64)  # sha256 hex

    def test_raw_token_authenticates(self):
        self.create_admin()
        raw = self.get_token()
        resp = self.client.get('/api/v1/jobs', headers=self.auth(raw))
        self.assertEqual(resp.status_code, 200)

    def test_revoked_token_rejected(self):
        self.create_admin()
        raw = self.get_token()
        resp = self.client.post('/api/v1/auth/revoke', headers=self.auth(raw))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get('/api/v1/jobs', headers=self.auth(raw))
        self.assertEqual(resp.status_code, 401)

    def test_refresh_rotates_token(self):
        self.create_admin()
        raw = self.get_token()
        resp = self.client.post('/api/v1/auth/refresh', headers=self.auth(raw),
                                json={'expiry_hours': 1})
        self.assertEqual(resp.status_code, 200)
        new_raw = resp.get_json()['data']['token']
        self.assertNotEqual(new_raw, raw)
        # old token was revoked
        self.assertEqual(self.client.get('/api/v1/jobs',
                                         headers=self.auth(raw)).status_code, 401)
        self.assertEqual(self.client.get('/api/v1/jobs',
                                         headers=self.auth(new_raw)).status_code, 200)


class TestAppSecurity(ApiTestBase):

    def test_api_exempt_from_csrf(self):
        self.create_admin()
        try:
            self.app.config['WTF_CSRF_ENABLED'] = True
            resp = self.client.post('/api/v1/auth/token',
                                    json={'username': 'admin@example.com',
                                          'password': 'password123'})
            self.assertEqual(resp.status_code, 201)
        finally:
            self.app.config['WTF_CSRF_ENABLED'] = False

    def test_secret_key_not_hardcoded(self):
        self.assertNotEqual(self.app.config['SECRET_KEY'], 'Big secret key')

    def test_cors_restricted_to_api(self):
        self.create_admin()
        token = self.get_token()
        headers = {'Origin': 'http://localhost:5173', **self.auth(token)}
        resp = self.client.get('/api/v1/jobs', headers=headers)
        self.assertEqual(resp.headers.get('Access-Control-Allow-Origin'),
                         'http://localhost:5173')
        headers = {'Origin': 'http://evil.example.com', **self.auth(token)}
        resp = self.client.get('/api/v1/jobs', headers=headers)
        self.assertNotEqual(resp.headers.get('Access-Control-Allow-Origin'),
                            'http://evil.example.com')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui/api/test_auth_security.py -v"`
Expected: FAIL (tokens stored plaintext, CSRF blocks POST, CORS wildcard, hardcoded key).

- [ ] **Step 3: Rewrite `arm/models/token.py`**

```python
"""
Token model for API authentication.

Tokens are stored SHA-256 hashed; the raw token is returned to the client
exactly once at issue time and never persisted.
"""
import datetime
import hashlib
import secrets

from arm.ui import db


def hash_token(raw_token: str) -> str:
    """SHA-256 hex digest of a raw token string."""
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


class Token(db.Model):
    """API tokens for external application authentication."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    expiry = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime,
                           default=lambda: datetime.datetime.now(datetime.timezone.utc))
    last_used = db.Column(db.DateTime)

    def is_expired(self):
        """True when the token is past its expiry."""
        return datetime.datetime.now(datetime.timezone.utc) > self.expiry

    def update_last_used(self):
        """Stamp last_used."""
        self.last_used = datetime.datetime.now(datetime.timezone.utc)
        db.session.commit()

    @staticmethod
    def issue(user_id, expiry_hours=24):
        """Create a token. Returns (raw_token, token_row)."""
        raw_token = secrets.token_urlsafe(32)
        token = Token(user_id=user_id, token_hash=hash_token(raw_token),
                      expiry_hours=expiry_hours)
        db.session.add(token)
        db.session.commit()
        return raw_token, token

    @staticmethod
    def validate_token(raw_token):
        """Validate a raw token; return its User or None."""
        from arm.models.user import User
        token = Token.query.filter_by(token_hash=hash_token(raw_token)).first()
        if token and not token.is_expired():
            token.update_last_used()
            return User.query.get(token.user_id)
        return None

    @staticmethod
    def revoke_token(raw_token):
        """Delete the token matching a raw token. Returns True when deleted."""
        token = Token.query.filter_by(token_hash=hash_token(raw_token)).first()
        if token:
            db.session.delete(token)
            db.session.commit()
            return True
        return False

    def __repr__(self):
        return f'<Token {self.id} for user {self.user_id}>'
```

Note: drop the custom `__init__` (SQLAlchemy default constructor + `issue()` cover all uses).

- [ ] **Step 4: Rewrite `arm/ui/api/v1/auth.py`**

```python
"""
API v1 Authentication routes (bearer tokens, hashed at rest).
"""
import bcrypt
from flask import request

from arm.models.user import User
from arm.models.token import Token

from . import api_v1
from .helpers import api_error, api_success


def get_bearer_token():
    """Return the raw bearer token from the request, or None."""
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1]
    return None


def require_token(function):
    """Decorator: require a valid Bearer token; store user on request."""
    def decorated_function(*args, **kwargs):
        raw_token = get_bearer_token()
        if not raw_token:
            return api_error('Missing or invalid authorization header',
                             401, 'unauthorized')
        user = Token.validate_token(raw_token)
        if not user:
            return api_error('Invalid or expired token', 401, 'unauthorized')
        setattr(request, 'api_user', user)
        return function(*args, **kwargs)
    decorated_function.__name__ = function.__name__
    return decorated_function


@api_v1.route('/auth/token', methods=['POST'])
def generate_token():
    """Exchange username/password for a new API token."""
    data = request.get_json(silent=True) or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return api_error('Username and password required', 400, 'validation_error')

    user = User.query.filter_by(email=username).first()
    if not user or not user.hash:
        return api_error('Invalid credentials', 401, 'unauthorized')
    try:
        login_hashed = bcrypt.hashpw(password.encode('utf-8'), user.hash)
    except (TypeError, ValueError):
        return api_error('Invalid credentials', 401, 'unauthorized')
    if login_hashed != user.password:
        return api_error('Invalid credentials', 401, 'unauthorized')

    expiry_hours = data.get('expiry_hours', 24)
    raw_token, token = Token.issue(user.user_id, expiry_hours)
    return api_success(
        data={'token': raw_token,
              'expiry': token.expiry.isoformat(),
              'user_id': user.user_id},
        status=201)


@api_v1.route('/auth/refresh', methods=['POST'])
@require_token
def refresh_token():
    """Rotate the presented token: revoke it and issue a new one."""
    raw_token = get_bearer_token()
    from flask import current_app
    current_token = Token.query.filter_by(
        token_hash=__import__('arm.models.token', fromlist=['hash_token']).hash_token(raw_token)
    ).first()
    if not current_token:
        return api_error('Token not found', 404, 'not_found')

    data = request.get_json(silent=True) or {}
    Token.revoke_token(raw_token)
    new_raw, new_token = Token.issue(current_token.user_id,
                                     data.get('expiry_hours', 24))
    return api_success(data={'token': new_raw,
                             'expiry': new_token.expiry.isoformat(),
                             'user_id': current_token.user_id})


@api_v1.route('/auth/revoke', methods=['POST'])
@require_token
def revoke_token():
    """Revoke the presented token."""
    raw_token = get_bearer_token()
    if Token.revoke_token(raw_token):
        return api_success(message='Token revoked successfully')
    return api_error('Token not found', 404, 'not_found')
```

Simplify the awkward import in `refresh_token` by adding `from arm.models.token import hash_token` at the top of the file and using `Token.query.filter_by(token_hash=hash_token(raw_token)).first()` directly.

- [ ] **Step 5: Harden `arm/ui/__init__.py`**

Make these exact edits:

```python
# top of file, extend imports
import secrets  # noqa: F401
```

Replace line 43-47 block:

```python
app = Flask(__name__)
csrf = CSRFProtect()
csrf.init_app(app)
CORS(app, resources={r"/*": {"origins": "*", "send_wildcard": "False"}})
socketio = SocketIO(app, cors_allowed_origins="*")
```

with:

```python
app = Flask(__name__)
csrf = CSRFProtect()
csrf.init_app(app)
# The SPA is same-origin in production; dev servers + custom origins come from env.
_cors_origins = [origin.strip() for origin
                 in os.environ.get('ARM_CORS_ORIGINS',
                                   'http://localhost:5173,http://127.0.0.1:5173').split(',')
                 if origin.strip()]
CORS(app, resources={r"/api/*": {"origins": _cors_origins}})
socketio = SocketIO(app, cors_allowed_origins=_cors_origins)
```

Replace line 56 (`app.config['SECRET_KEY'] = "Big secret key"  # TODO: make this random!`):

```python
# Sessions invalidate on restart unless ARM_SECRET_KEY is set in the environment
app.config['SECRET_KEY'] = os.environ.get('ARM_SECRET_KEY') or secrets.token_hex(32)
```

After `app.register_blueprint(api_v1)` (line ~86) add:

```python
# The API authenticates via Bearer tokens (not cookies), so CSRF does not apply
csrf.exempt(api_v1)
```

- [ ] **Step 6: Delete unused schemas.py**

```bash
git rm arm/ui/api/v1/schemas.py
```

- [ ] **Step 7: Run tests**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui -v && python3 -m flake8 arm/ui/api arm/models"`
Expected: all pass, flake8 clean.

- [ ] **Step 8: Commit**

```bash
git add arm/ui/__init__.py arm/models/token.py arm/ui/api/v1/auth.py test/unittest/ui
git commit -m "fix(api): hashed bearer tokens, CSRF exempt /api/v1, env SECRET_KEY, scoped CORS"
```

---

### Task 4: Real job actions (abandon / fixperms / send)

**Files:**
- Modify: `arm/ui/api/v1/jobs.py` (replace the two stub branches; abandon already real since Task 2)
- Test: `test/unittest/ui/api/test_job_actions.py`

**Interfaces:**
- Consumes: `arm.ui.utils.fix_permissions(job_id) -> dict` (has `'success'` key), `arm.ui.utils.send_to_remote_db(job_id) -> dict` (has `'success'` key).

- [ ] **Step 1: Write failing tests**

`test/unittest/ui/api/test_job_actions.py`:

```python
"""Job actions: abandon, fixperms, send."""
from unittest.mock import patch

from test.unittest.ui.api.base import ApiTestBase


class TestJobActions(ApiTestBase):

    def setUp(self):
        super().setUp()
        self.create_admin()
        self.token = self.get_token()

    def test_missing_action_400(self):
        job = self.make_job()
        resp = self.client.post(f'/api/v1/jobs/{job.job_id}/actions',
                                headers=self.auth(self.token), json={})
        self.assertEqual(resp.status_code, 400)

    def test_unknown_action_400(self):
        job = self.make_job()
        resp = self.client.post(f'/api/v1/jobs/{job.job_id}/actions',
                                headers=self.auth(self.token),
                                json={'action': 'explode'})
        self.assertEqual(resp.status_code, 400)

    def test_fixperms_calls_helper(self):
        job = self.make_job()
        with patch('arm.ui.api.v1.jobs.fix_permissions',
                   return_value={'success': True}) as mocked:
            resp = self.client.post(f'/api/v1/jobs/{job.job_id}/actions',
                                    headers=self.auth(self.token),
                                    json={'action': 'fixperms'})
        self.assertEqual(resp.status_code, 200)
        mocked.assert_called_once_with(str(job.job_id))

    def test_fixperms_failure_500(self):
        job = self.make_job()
        with patch('arm.ui.api.v1.jobs.fix_permissions',
                   return_value={'success': False, 'Error': 'boom'}):
            resp = self.client.post(f'/api/v1/jobs/{job.job_id}/actions',
                                    headers=self.auth(self.token),
                                    json={'action': 'fixperms'})
        self.assertEqual(resp.status_code, 500)

    def test_send_calls_helper(self):
        job = self.make_job()
        with patch('arm.ui.api.v1.jobs.send_to_remote_db',
                   return_value={'success': True}) as mocked:
            resp = self.client.post(f'/api/v1/jobs/{job.job_id}/actions',
                                    headers=self.auth(self.token),
                                    json={'action': 'send'})
        self.assertEqual(resp.status_code, 200)
        mocked.assert_called_once_with(str(job.job_id))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui/api/test_job_actions.py -v"`
Expected: FAIL (`fixperms`/`send` return fake success without calling helpers).

- [ ] **Step 3: Implement**

In `arm/ui/api/v1/jobs.py`: add imports `import arm.ui.utils as ui_utils` and `from arm.ui.json_api import terminate_process` (move the local import out of the branch). Replace the two stub branches:

```python
        if action == 'fixperms':
            result = ui_utils.fix_permissions(str(job.job_id))
            if result.get('success'):
                return api_success(message=f'Permissions fixed for job {job_id}',
                                   data={'folder': result.get('folder')})
            return api_error(result.get('Error', 'Failed to fix permissions'),
                             500, 'fixperms_error')

        if action == 'send':
            result = ui_utils.send_to_remote_db(str(job.job_id))
            if result.get('success'):
                return api_success(message=f'Job {job_id} sent to remote database')
            return api_error('Failed to send job to remote database',
                             500, 'send_error')
```

- [ ] **Step 4: Run tests**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui -v"`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add arm/ui/api/v1/jobs.py test/unittest/ui/api/test_job_actions.py
git commit -m "feat(api): implement fixperms/send job actions via shared helpers"
```

---

### Task 5: Metadata search/details + job title/tracks/params endpoints

**Files:**
- Create: `arm/ui/api/v1/metadata.py`
- Modify: `arm/ui/api/v1/__init__.py` (add `metadata` to the import list)
- Modify: `arm/ui/api/v1/jobs.py` (add three PUT routes)
- Test: `test/unittest/ui/api/test_metadata_and_titles.py`

**Interfaces:**
- Consumes: `ui_utils.metadata_selector(func, query, year, imdb_id)`, `ui_utils.clean_for_filename(string)`.
- Produces: `GET /api/v1/metadata/search?title=&year=`, `GET /api/v1/metadata/details?imdb_id=`, `PUT /api/v1/jobs/<id>/title`, `PUT /api/v1/jobs/<id>/tracks`, `PUT /api/v1/jobs/<id>/params`.

- [ ] **Step 1: Write failing tests**

`test/unittest/ui/api/test_metadata_and_titles.py`:

```python
"""Metadata provider + title/track/param mutation endpoints."""
from unittest.mock import patch

from test.unittest.ui.api.base import ApiTestBase


class TestMetadata(ApiTestBase):

    def setUp(self):
        super().setUp()
        self.create_admin()
        self.token = self.get_token()

    def test_search_requires_title(self):
        resp = self.client.get('/api/v1/metadata/search', headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 400)

    def test_search_returns_results(self):
        with patch('arm.ui.api.v1.metadata.ui_utils.metadata_selector',
                   return_value={'Search': [{'Title': 'Coco', 'Year': '2017'}]}) as mocked:
            resp = self.client.get('/api/v1/metadata/search?title=Coco&year=2017',
                                   headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['data']['Search'][0]['Title'], 'Coco')
        mocked.assert_called_once_with('search', 'Coco', '2017')

    def test_search_retries_without_year_on_empty(self):
        calls = []
        selector = lambda func, q, y: (calls.append((q, y)),
                                       {'Search': []})[1]  # noqa: E731
        with patch('arm.ui.api.v1.metadata.ui_utils.metadata_selector', side_effect=selector):
            resp = self.client.get('/api/v1/metadata/search?title=Coco&year=2017',
                                   headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(calls, [('Coco', '2017'), ('Coco', '')])

    def test_details_requires_imdb(self):
        resp = self.client.get('/api/v1/metadata/details', headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 400)

    def test_details_not_found(self):
        with patch('arm.ui.api.v1.metadata.ui_utils.metadata_selector',
                   return_value={'Error': 'not found'}):
            resp = self.client.get('/api/v1/metadata/details?imdb_id=tt0000000',
                                   headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 404)


class TestJobTitleTracksParams(ApiTestBase):

    def setUp(self):
        super().setUp()
        self.create_admin()
        self.token = self.get_token()
        self.job = self.make_job(title='Wrong Title', year='1999')

    def test_update_title(self):
        resp = self.client.put(f'/api/v1/jobs/{self.job.job_id}/title',
                               headers=self.auth(self.token),
                               json={'title': 'Coco', 'year': '2017',
                                     'video_type': 'movie', 'imdb_id': 'tt2380307'})
        self.assertEqual(resp.status_code, 200)
        self.db.session.expire_all()
        job = self.db.session.get(type(self.job), self.job.job_id)
        self.assertEqual(job.title, 'Coco')
        self.assertEqual(job.title_manual, 'Coco')
        self.assertEqual(job.year, '2017')
        self.assertEqual(job.imdb_id, 'tt2380307')
        self.assertTrue(job.hasnicetitle)

    def test_update_title_requires_title(self):
        resp = self.client.put(f'/api/v1/jobs/{self.job.job_id}/title',
                               headers=self.auth(self.token), json={'year': '2017'})
        self.assertEqual(resp.status_code, 400)

    def test_update_title_unknown_job_404(self):
        resp = self.client.put('/api/v1/jobs/9999/title',
                               headers=self.auth(self.token), json={'title': 'X'})
        self.assertEqual(resp.status_code, 404)

    def test_update_tracks(self):
        from arm.models.track import Track
        track = Track(job_id=self.job.job_id, track_number='1', length=100,
                      aspect_ratio='16:9', fps=23.976, main_feature=False,
                      source='makemkv', basename='t00', filename='t00.mkv')
        self.db.session.add(track)
        self.db.session.commit()
        self.job.status = 'waiting'
        self.job.manual_mode = True
        self.db.session.commit()

        resp = self.client.put(f'/api/v1/jobs/{self.job.job_id}/tracks',
                               headers=self.auth(self.token),
                               json={'tracks': [{'track_id': track.track_id,
                                                 'process': True}]})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(track.process)
        self.assertTrue(self.job.manual_start)

    def test_update_tracks_unknown_track_404(self):
        resp = self.client.put(f'/api/v1/jobs/{self.job.job_id}/tracks',
                               headers=self.auth(self.token),
                               json={'tracks': [{'track_id': 999, 'process': True}]})
        self.assertEqual(resp.status_code, 404)

    def test_update_tracks_validation(self):
        resp = self.client.put(f'/api/v1/jobs/{self.job.job_id}/tracks',
                               headers=self.auth(self.token), json={'tracks': 'nope'})
        self.assertEqual(resp.status_code, 400)

    def test_update_params(self):
        from arm.models.config import Config
        self.job.config = Config(job_id=self.job.job_id)
        self.db.session.commit()
        resp = self.client.put(f'/api/v1/jobs/{self.job.job_id}/params',
                               headers=self.auth(self.token),
                               json={'disctype': 'bluray', 'main_feature': True,
                                     'minlength': '600', 'maxlength': '99999'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.job.disctype, 'bluray')
        self.assertEqual(self.job.config.MAINFEATURE, 1)

    def test_update_params_invalid_disctype(self):
        resp = self.client.put(f'/api/v1/jobs/{self.job.job_id}/params',
                               headers=self.auth(self.token),
                               json={'disctype': 'laserdisc'})
        self.assertEqual(resp.status_code, 400)
```

Note: check `Config.__init__` signature before writing the params test — if it requires arguments, adapt (pass the same args the ripper passes when creating a per-job Config; worst case construct via `Config.__new__(Config)` + set `job_id`, mirroring `make_job`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui/api/test_metadata_and_titles.py -v"`
Expected: FAIL (404/405 — routes do not exist).

- [ ] **Step 3: Implement `metadata.py`**

```python
"""API v1 metadata provider routes (OMDB/TMDB search and details)."""
from flask import request

import arm.ui.utils as ui_utils

from . import api_v1
from .auth import require_token
from .helpers import api_error, api_success


def _results_empty(results):
    return (results is None
            or 'Error' in results
            or ('Search' in results and len(results['Search']) < 1))


@api_v1.route('/metadata/search', methods=['GET'])
@require_token
def metadata_search():
    """Search the configured metadata provider. Retries without year when empty."""
    title = (request.args.get('title') or '').strip()
    year = (request.args.get('year') or '').strip()
    if not title:
        return api_error('title is required', 400, 'validation_error')

    results = ui_utils.metadata_selector('search', title, year)
    if _results_empty(results):
        results = ui_utils.metadata_selector('search', title, '')
    if _results_empty(results):
        return api_success(data={'Search': []}, message='No results found')
    return api_success(data=results)


@api_v1.route('/metadata/details', methods=['GET'])
@require_token
def metadata_details():
    """Full metadata for one imdb_id (mirrors legacy gettitle)."""
    imdb_id = (request.args.get('imdb_id') or '').strip()
    if not imdb_id:
        return api_error('imdb_id is required', 400, 'validation_error')
    results = ui_utils.metadata_selector('get_details', None, None, imdb_id)
    if _results_empty(results):
        return api_error('No metadata found for that imdb_id', 404, 'not_found')
    return api_success(data=results)
```

Add `metadata` to the module import list in `arm/ui/api/v1/__init__.py`:

```python
from . import auth, jobs, config, system, notifications, websockets, metadata  # noqa: E402,F401
```

- [ ] **Step 4: Add PUT routes to `jobs.py`**

Append to `arm/ui/api/v1/jobs.py` (needs `from arm.models.notifications import Notifications`, `from arm.models.job import JobState`, `import arm.ui.utils as ui_utils` at top):

```python
@api_v1.route('/jobs/<int:job_id>/title', methods=['PUT'])
@require_token
def update_job_title(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Update job title metadata (mirrors legacy updatetitle/customTitle)."""
    try:
        job, error = get_job_or_404(job_id)
        if error:
            return error
        data = request.get_json(silent=True) or {}
        if not data.get('title'):
            return api_error('title is required', 400, 'validation_error')

        old_title, old_year = job.title, job.year
        new_title = ui_utils.clean_for_filename(str(data['title']))
        job.title = job.title_manual = new_title
        if 'year' in data:
            job.year = job.year_manual = str(data['year'])
        if 'video_type' in data:
            job.video_type = job.video_type_manual = str(data['video_type'])
        if 'imdb_id' in data:
            job.imdb_id = job.imdb_id_manual = str(data['imdb_id'])
        if 'poster_url' in data:
            job.poster_url = job.poster_url_manual = str(data['poster_url'])
        job.hasnicetitle = True

        notification = Notifications(
            f'Job: {job.job_id} was updated',
            f'Title: {old_title} ({old_year}) was updated to '
            f'{new_title} ({job.year})')
        db.session.add(notification)
        db.session.commit()
        return api_success(data=job.get_d(), message='Title updated')
    except SQLAlchemyError as err:
        current_app.logger.error(f'Database error updating title for job {job_id}: {err}')
        db.session.rollback()
        return api_error('Database error', 500, 'database_error')


@api_v1.route('/jobs/<int:job_id>/tracks', methods=['PUT'])
@require_token
def update_job_tracks(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Set which tracks get ripped (mirrors legacy jobdetailload)."""
    try:
        job, error = get_job_or_404(job_id)
        if error:
            return error
        data = request.get_json(silent=True) or {}
        tracks = data.get('tracks')
        if not isinstance(tracks, list):
            return api_error('tracks must be a list of {track_id, process}',
                             400, 'validation_error')

        updated = 0
        for entry in tracks:
            if not isinstance(entry, dict) or 'track_id' not in entry:
                return api_error('each track entry needs a track_id',
                                 400, 'validation_error')
            db_track = job.tracks.filter_by(track_id=entry['track_id']).first()
            if not db_track:
                return api_error(
                    f"Track {entry['track_id']} not found on job {job_id}",
                    404, 'not_found')
            db_track.process = bool(entry.get('process', False))
            updated += 1

        if (job.manual_mode
                and job.status == JobState.MANUAL_WAIT_STARTED.value
                and not job.manual_start):
            job.manual_start = True
        db.session.commit()
        return api_success(data={'updated': updated,
                                 'manual_start': bool(job.manual_start)})
    except SQLAlchemyError as err:
        current_app.logger.error(f'Database error updating tracks for job {job_id}: {err}')
        db.session.rollback()
        return api_error('Database error', 500, 'database_error')


@api_v1.route('/jobs/<int:job_id>/params', methods=['PUT'])
@require_token
def update_job_params(job_id: int) -> Union[Response, Tuple[Response, int]]:
    """Update rip parameters for a waiting job (mirrors legacy changeparams)."""
    try:
        job, error = get_job_or_404(job_id)
        if error:
            return error
        if not job.config:
            return api_error('Job has no config', 404, 'not_found')
        data = request.get_json(silent=True) or {}
        config = job.config

        if 'disctype' in data:
            if data['disctype'] not in ('dvd', 'bluray', 'music', 'data'):
                return api_error('invalid disctype', 400, 'validation_error')
            job.disctype = str(data['disctype'])
        if 'minlength' in data:
            cfg.arm_config['MINLENGTH'] = config.MINLENGTH = str(data['minlength'])
        if 'maxlength' in data:
            cfg.arm_config['MAXLENGTH'] = config.MAXLENGTH = str(data['maxlength'])
        if 'rip_method' in data:
            if data['rip_method'] not in ('mkv', 'backup'):
                return api_error('invalid rip_method', 400, 'validation_error')
            cfg.arm_config['RIPMETHOD'] = config.RIPMETHOD = str(data['rip_method'])
        if 'main_feature' in data:
            cfg.arm_config['MAINFEATURE'] = config.MAINFEATURE = \
                1 if data['main_feature'] else 0

        notification = Notifications(
            f'Job: {job.job_id} Config updated!',
            f'Parameters changed. Rip Method={config.RIPMETHOD}, '
            f'Main Feature={config.MAINFEATURE}, '
            f'Minimum Length={config.MINLENGTH}, '
            f'Maximum Length={config.MAXLENGTH}, Disctype={job.disctype}')
        db.session.add(notification)
        db.session.commit()
        return api_success(data={'job': job.get_d(), 'config': config.get_d()},
                           message='Parameters updated')
    except SQLAlchemyError as err:
        current_app.logger.error(f'Database error updating params for job {job_id}: {err}')
        db.session.rollback()
        return api_error('Database error', 500, 'database_error')
```

- [ ] **Step 5: Run tests**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui -v && python3 -m flake8 arm/ui/api"`
Expected: all pass, flake8 clean.

- [ ] **Step 6: Commit**

```bash
git add arm/ui/api/v1 test/unittest/ui/api/test_metadata_and_titles.py
git commit -m "feat(api): metadata search/details + job title/tracks/params endpoints"
```

---

### Task 6: History endpoint

**Files:**
- Create: `arm/ui/api/v1/history.py`
- Modify: `arm/ui/api/v1/__init__.py` (add `history` import)
- Test: `test/unittest/ui/api/test_history.py`

**Interfaces:**
- Produces: `GET /api/v1/history?status=success|fail&search=&page=&per_page=` — finished jobs only, ordered by stop_time desc.

- [ ] **Step 1: Write failing tests**

`test/unittest/ui/api/test_history.py`:

```python
"""History listing endpoint."""
from test.unittest.ui.api.base import ApiTestBase


class TestHistory(ApiTestBase):

    def setUp(self):
        super().setUp()
        self.create_admin()
        self.token = self.get_token()

    def test_history_only_finished_jobs(self):
        self.make_job(status='success', title='Good')
        self.make_job(status='fail', title='Bad')
        self.make_job(status='active', title='Running')
        resp = self.client.get('/api/v1/history', headers=self.auth(self.token))
        body = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body['meta']['total'], 2)
        titles = {job['title'] for job in body['data']}
        self.assertEqual(titles, {'Good', 'Bad'})

    def test_history_status_filter(self):
        self.make_job(status='success')
        self.make_job(status='fail')
        resp = self.client.get('/api/v1/history?status=fail',
                               headers=self.auth(self.token))
        body = resp.get_json()
        self.assertEqual(body['meta']['total'], 1)
        self.assertEqual(body['data'][0]['status'], 'fail')

    def test_history_invalid_status_400(self):
        resp = self.client.get('/api/v1/history?status=whatever',
                               headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 400)

    def test_history_search(self):
        self.make_job(status='success', title='Finding Nemo')
        self.make_job(status='success', title='Coco')
        resp = self.client.get('/api/v1/history?search=nemo',
                               headers=self.auth(self.token))
        body = resp.get_json()
        self.assertEqual(body['meta']['total'], 1)
        self.assertEqual(body['data'][0]['title'], 'Finding Nemo')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui/api/test_history.py -v"`
Expected: FAIL (404).

- [ ] **Step 3: Implement**

`arm/ui/api/v1/history.py`:

```python
"""API v1 job history routes (finished jobs)."""
from flask import request
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError

from arm.models.job import Job

from . import api_v1
from .auth import require_token
from .helpers import api_error, api_success, pagination_meta, parse_pagination


@api_v1.route('/history', methods=['GET'])
@require_token
def get_history():
    """List finished jobs with optional status/search filters + pagination."""
    try:
        pagination = parse_pagination()
        if pagination is None:
            return api_error('Invalid pagination parameters', 400, 'validation_error')
        page, per_page = pagination

        query = Job.query.filter(Job.status.in_(('success', 'fail')))
        status = request.args.get('status')
        if status:
            if status not in ('success', 'fail'):
                return api_error(f'Invalid status: {status}', 400, 'validation_error')
            query = query.filter_by(status=status)

        search = request.args.get('search')
        if search:
            pattern = f"%{search}%"
            query = query.filter((Job.title.like(pattern))
                                 | (Job.title_auto.like(pattern))
                                 | (Job.title_manual.like(pattern)))

        query = query.order_by(desc(Job.stop_time), desc(Job.job_id))
        total = query.count()
        jobs = query.offset((page - 1) * per_page).limit(per_page).all()
        return api_success(data=[job.get_d() for job in jobs],
                           meta=pagination_meta(total, page, per_page))
    except SQLAlchemyError as err:
        from flask import current_app
        current_app.logger.error(f'Database error getting history: {err}')
        return api_error('Database error', 500, 'database_error')
```

Add `history` to the import list in `arm/ui/api/v1/__init__.py`.

- [ ] **Step 4: Run tests + commit**

```bash
wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui -v"
git add arm/ui/api/v1/history.py arm/ui/api/v1/__init__.py test/unittest/ui/api/test_history.py
git commit -m "feat(api): history endpoint for finished jobs"
```

---

### Task 7: Logs endpoints

**Files:**
- Create: `arm/ui/api/v1/logs.py`
- Modify: `arm/ui/api/v1/__init__.py` (add `logs` import)
- Test: `test/unittest/ui/api/test_logs.py`

**Interfaces:**
- Produces: `GET /api/v1/logs` and `GET /api/v1/logs/<filename>?lines=N` (default 200, max 2000).

- [ ] **Step 1: Write failing tests**

`test/unittest/ui/api/test_logs.py`:

```python
"""Log listing/tail endpoints."""
import os

from test.unittest.ui.api.base import ApiTestBase


class TestLogs(ApiTestBase):

    def setUp(self):
        super().setUp()
        self.create_admin()
        self.token = self.get_token()

    def test_list_logs(self):
        import arm.config.config as cfg
        log_dir = cfg.arm_config['LOGPATH']
        for name in ('aaa.log', 'bbb.log', 'notes.txt'):
            with open(os.path.join(log_dir, name), 'w', encoding='utf-8') as fh:
                fh.write('line\n')
        resp = self.client.get('/api/v1/logs', headers=self.auth(self.token))
        body = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        names = [item['name'] for item in body['data']]
        self.assertIn('aaa.log', names)
        self.assertIn('bbb.log', names)
        self.assertNotIn('notes.txt', names)

    def test_read_log_tail(self):
        import arm.config.config as cfg
        with open(os.path.join(cfg.arm_config['LOGPATH'], 'tail.log'), 'w',
                  encoding='utf-8') as fh:
            fh.write('\n'.join(f'line{i}' for i in range(100)))
        resp = self.client.get('/api/v1/logs/tail.log?lines=5',
                               headers=self.auth(self.token))
        body = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body['data']['content'].splitlines()[0], 'line95')

    def test_read_log_missing_404(self):
        resp = self.client.get('/api/v1/logs/nope.log', headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 404)

    def test_path_traversal_rejected(self):
        resp = self.client.get('/api/v1/logs/..%2f..%2fetc%2fpasswd',
                               headers=self.auth(self.token))
        self.assertIn(resp.status_code, (400, 404))

    def test_non_log_extension_rejected(self):
        resp = self.client.get('/api/v1/logs/arm.yaml', headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 400)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui/api/test_logs.py -v"`
Expected: FAIL (404).

- [ ] **Step 3: Implement**

`arm/ui/api/v1/logs.py`:

```python
"""API v1 log file routes."""
import os
from collections import deque
from datetime import datetime

from flask import request

import arm.config.config as cfg

from . import api_v1
from .auth import require_token
from .helpers import api_error, api_success

MAX_LINES = 2000


@api_v1.route('/logs', methods=['GET'])
@require_token
def list_logs():
    """List .log files in the ARM log directory, newest first."""
    log_dir = cfg.arm_config['LOGPATH']
    if not os.path.isdir(log_dir):
        return api_error('Log path not found', 404, 'not_found')
    logs = []
    for name in os.listdir(log_dir):
        if not name.endswith('.log'):
            continue
        full_path = os.path.join(log_dir, name)
        if not os.path.isfile(full_path):
            continue
        stat = os.stat(full_path)
        logs.append({'name': name,
                     'size': stat.st_size,
                     'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()})
    logs.sort(key=lambda item: item['modified'], reverse=True)
    return api_success(data=logs)


@api_v1.route('/logs/<path:filename>', methods=['GET'])
@require_token
def read_log(filename):
    """Tail a single log file (?lines=N, default 200, max 2000)."""
    if filename != os.path.basename(filename) or '..' in filename:
        return api_error('Invalid log filename', 400, 'validation_error')
    if not filename.endswith('.log'):
        return api_error('Only .log files can be read', 400, 'validation_error')

    try:
        lines_wanted = int(request.args.get('lines', 200))
    except (TypeError, ValueError):
        return api_error('lines must be an integer', 400, 'validation_error')
    lines_wanted = min(max(1, lines_wanted), MAX_LINES)

    full_path = os.path.join(cfg.arm_config['LOGPATH'], filename)
    if not os.path.isfile(full_path):
        return api_error('Log file not found', 404, 'not_found')
    try:
        with open(full_path, encoding='utf8', errors='ignore') as handle:
            content = ''.join(deque(handle, maxlen=lines_wanted))
    except OSError:
        return api_error('Could not read log file', 500, 'io_error')
    return api_success(data={'name': filename, 'lines': lines_wanted,
                             'content': content})
```

Add `logs` to the import list in `arm/ui/api/v1/__init__.py`.

- [ ] **Step 4: Run tests + commit**

```bash
wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui -v"
git add arm/ui/api/v1/logs.py arm/ui/api/v1/__init__.py test/unittest/ui/api/test_logs.py
git commit -m "feat(api): log listing and tail endpoints"
```

---

### Task 8: Settings endpoints (arm.yaml / UI / abcde / apprise)

**Files:**
- Create: `arm/ui/api/v1/settings_api.py`
- Modify: `arm/ui/api/v1/__init__.py` (add `settings_api` import)
- Test: `test/unittest/ui/api/test_settings.py`

**Interfaces:**
- Consumes: `ui_utils.generate_comments()`, `ui_utils.build_arm_cfg(form_data, comments)`, `ui_utils.build_apprise_cfg(form_data)`, `arm.ripper.utils.notify(args, title, message)`, `cfg.arm_config_path`, `cfg.abcde_config_path`, `cfg.apprise_config_path`.
- Produces: `GET/PUT /api/v1/settings/ui`, `GET/PUT /api/v1/settings/arm`, `GET/PUT /api/v1/settings/abcde`, `GET/PUT /api/v1/settings/apprise`, `POST /api/v1/settings/apprise/test`. Secret-bearing arm.yaml values are masked on GET (`****last4`) and masked echoes are ignored on PUT.

- [ ] **Step 1: Write failing tests**

`test/unittest/ui/api/test_settings.py`:

```python
"""Settings endpoints."""
from unittest.mock import patch

from test.unittest.ui.api.base import ApiTestBase
from arm.models.ui_settings import UISettings


class TestUiSettings(ApiTestBase):

    def setUp(self):
        super().setUp()
        self.create_admin()
        self.token = self.get_token()
        self.db.session.add(UISettings(use_icons=True, save_remote_images=False,
                                       bootstrap_skin='flatly', language='en',
                                       index_refresh=6500, database_limit=2500,
                                       notify_refresh=6500))
        self.db.session.commit()

    def test_get_ui_settings(self):
        resp = self.client.get('/api/v1/settings/ui', headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['data']['index_refresh'], '6500')

    def test_put_ui_settings(self):
        resp = self.client.put('/api/v1/settings/ui', headers=self.auth(self.token),
                               json={'index_refresh': 3000, 'database_limit': 100})
        self.assertEqual(resp.status_code, 200)
        ui_cfg = UISettings.query.get(1)
        self.assertEqual(ui_cfg.index_refresh, 3000)
        self.assertEqual(ui_cfg.database_limit, 100)

    def test_put_ui_settings_invalid_value(self):
        resp = self.client.put('/api/v1/settings/ui', headers=self.auth(self.token),
                               json={'index_refresh': 'soon'})
        self.assertEqual(resp.status_code, 400)


class TestArmSettings(ApiTestBase):

    def setUp(self):
        super().setUp()
        self.create_admin()
        self.token = self.get_token()

    def test_get_masks_secrets(self):
        import arm.config.config as cfg
        cfg.arm_config['ARM_API_KEY'] = 'supersecret123'
        resp = self.client.get('/api/v1/settings/arm', headers=self.auth(self.token))
        masked = resp.get_json()['data']['ARM_API_KEY']
        self.assertNotEqual(masked, 'supersecret123')
        self.assertTrue(masked.startswith('*'))
        self.assertTrue(masked.endswith('t123'))

    def test_put_writes_yaml(self):
        with patch('arm.ui.api.v1.settings_api.ui_utils.generate_comments',
                   return_value={}), \
             patch('arm.ui.api.v1.settings_api.ui_utils.build_arm_cfg',
                   return_value='WEBSERVER_PORT: 8081\n') as build:
            resp = self.client.put('/api/v1/settings/arm', headers=self.auth(self.token),
                                   json={'WEBSERVER_PORT': '8081'})
        self.assertEqual(resp.status_code, 200)
        build.assert_called_once()
        import arm.config.config as cfg
        with open(cfg.arm_config_path, encoding='utf-8') as fh:
            self.assertIn('WEBSERVER_PORT: 8081', fh.read())

    def test_put_ignores_masked_echo(self):
        with patch('arm.ui.api.v1.settings_api.ui_utils.generate_comments',
                   return_value={}), \
             patch('arm.ui.api.v1.settings_api.ui_utils.build_arm_cfg',
                   return_value='x: 1\n') as build:
            self.client.put('/api/v1/settings/arm', headers=self.auth(self.token),
                            json={'ARM_API_KEY': '****t123', 'WEBSERVER_PORT': '8081'})
        merged = build.call_args[0][0]
        self.assertEqual(merged['ARM_API_KEY'], cfg_current_api_key())
        self.assertEqual(merged['WEBSERVER_PORT'], '8081')


def cfg_current_api_key():
    import arm.config.config as cfg
    return cfg.arm_config.get('ARM_API_KEY')


class TestAbcdeAndApprise(ApiTestBase):

    def setUp(self):
        super().setUp()
        self.create_admin()
        self.token = self.get_token()

    def test_abcde_roundtrip(self):
        resp = self.client.put('/api/v1/settings/abcde', headers=self.auth(self.token),
                               json={'content': 'CDDBMETHOD=musicbrainz\r\nX=Y'})
        self.assertEqual(resp.status_code, 200)
        import arm.config.config as cfg
        self.assertNotIn('\r', cfg.abcde_config)
        resp = self.client.get('/api/v1/settings/abcde', headers=self.auth(self.token))
        self.assertIn('CDDBMETHOD=musicbrainz', resp.get_json()['data']['content'])

    def test_apprise_test_sends_notification(self):
        with patch('arm.ui.api.v1.settings_api.ripper_utils.notify') as mocked:
            resp = self.client.post('/api/v1/settings/apprise/test',
                                    headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 200)
        mocked.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui/api/test_settings.py -v"`
Expected: FAIL (404).

- [ ] **Step 3: Implement**

`arm/ui/api/v1/settings_api.py`:

```python
"""API v1 settings routes: arm.yaml, UI settings, abcde.conf, apprise."""
import importlib

from flask import request

import arm.config.config as cfg
import arm.ui.utils as ui_utils
from arm.models.ui_settings import UISettings
from arm.ripper import utils as ripper_utils
from arm.ui import db

from . import api_v1
from .auth import require_token
from .helpers import api_error, api_success

SECRET_MARKERS = ('PASS', 'KEY', 'SECRET', 'TOKEN', 'API')

UI_SETTINGS_FIELDS = {
    'use_icons': bool,
    'save_remote_images': bool,
    'bootstrap_skin': str,
    'language': str,
    'index_refresh': int,
    'database_limit': int,
    'notify_refresh': int,
}


def mask_value(value):
    """Mask a secret, leaving the last 4 chars visible (mirrors settings.py)."""
    value = str(value)
    if len(value) <= 4:
        return '****'
    return value[-4:].rjust(len(value), '*')


def is_masked(value):
    """Detect a masked echo from GET /settings/arm."""
    return (isinstance(value, str) and value.startswith('*')
            and len(value.lstrip('*')) <= 4)


@api_v1.route('/settings/ui', methods=['GET'])
@require_token
def get_ui_settings():
    """Current UI settings row."""
    ui_cfg = UISettings.query.get(1)
    if not ui_cfg:
        return api_error('UI settings not found', 404, 'not_found')
    return api_success(data=ui_cfg.get_d())


@api_v1.route('/settings/ui', methods=['PUT'])
@require_token
def update_ui_settings():
    """Update UI settings (mirrors legacy save_ui_settings)."""
    ui_cfg = UISettings.query.get(1)
    if not ui_cfg:
        return api_error('UI settings not found', 404, 'not_found')
    data = request.get_json(silent=True) or {}
    updated = []
    for field, field_type in UI_SETTINGS_FIELDS.items():
        if field not in data:
            continue
        raw = data[field]
        if field_type is bool:
            value = (str(raw).strip().lower() == 'true'
                     if isinstance(raw, str) else bool(raw))
        else:
            try:
                value = field_type(raw)
            except (TypeError, ValueError):
                return api_error(f'Invalid value for {field}', 400, 'validation_error')
        setattr(ui_cfg, field, value)
        updated.append(field)
    if not updated:
        return api_error('No valid fields to update', 400, 'validation_error')
    db.session.commit()
    return api_success(data=ui_cfg.get_d(), message='UI settings updated')


@api_v1.route('/settings/arm', methods=['GET'])
@require_token
def get_arm_settings():
    """Current arm.yaml values with secrets masked."""
    masked = {}
    for key, value in cfg.arm_config.items():
        if value and any(marker in key.upper() for marker in SECRET_MARKERS):
            masked[key] = mask_value(value)
        else:
            masked[key] = value
    return api_success(data=masked)


@api_v1.route('/settings/arm', methods=['PUT'])
@require_token
def update_arm_settings():
    """Write updated values to arm.yaml (mirrors legacy save_settings)."""
    data = request.get_json(silent=True) or {}
    if not data:
        return api_error('No settings provided', 400, 'validation_error')
    # Ignore masked values echoed back from GET
    data = {key: value for key, value in data.items() if not is_masked(value)}

    merged = dict(cfg.arm_config)
    merged.update(data)
    comments = ui_utils.generate_comments()
    new_cfg = ui_utils.build_arm_cfg(merged, comments)
    try:
        with open(cfg.arm_config_path, 'w', encoding='utf-8') as settings_file:
            settings_file.write(new_cfg)
    except OSError:
        return api_error(f'{cfg.arm_config_path} is read-only', 403, 'read_only')
    importlib.reload(cfg)
    return api_success(message='arm.yaml updated')


@api_v1.route('/settings/abcde', methods=['GET'])
@require_token
def get_abcde_settings():
    """Raw abcde.conf content."""
    return api_success(data={'content': cfg.abcde_config})


@api_v1.route('/settings/abcde', methods=['PUT'])
@require_token
def update_abcde_settings():
    """Overwrite abcde.conf (mirrors legacy save_abcde, strips CR)."""
    data = request.get_json(silent=True) or {}
    if 'content' not in data:
        return api_error('content is required', 400, 'validation_error')
    clean = '\n'.join(str(data['content']).splitlines())
    try:
        with open(cfg.abcde_config_path, 'w', encoding='utf-8') as abcde_file:
            abcde_file.write(clean)
    except OSError:
        return api_error(f'{cfg.abcde_config_path} is read-only', 403, 'read_only')
    cfg.abcde_config = clean
    return api_success(message='abcde.conf updated')


@api_v1.route('/settings/apprise', methods=['GET'])
@require_token
def get_apprise_settings():
    """Parsed apprise.yaml content."""
    return api_success(data=cfg.apprise_config)


@api_v1.route('/settings/apprise', methods=['PUT'])
@require_token
def update_apprise_settings():
    """Write apprise.yaml (mirrors legacy save_apprise_cfg)."""
    data = request.get_json(silent=True) or {}
    if not data:
        return api_error('No apprise settings provided', 400, 'validation_error')
    new_cfg = ui_utils.build_apprise_cfg(data)
    try:
        with open(cfg.apprise_config_path, 'w', encoding='utf-8') as settings_file:
            settings_file.write(new_cfg)
    except OSError:
        return api_error(f'{cfg.apprise_config_path} is read-only', 403, 'read_only')
    importlib.reload(cfg)
    return api_success(message='apprise.yaml updated')


@api_v1.route('/settings/apprise/test', methods=['POST'])
@require_token
def test_apprise():
    """Send a test notification via apprise (mirrors legacy testapprise)."""
    message = 'This is a notification by the ARM-Notification Test!'
    if cfg.arm_config.get('UI_BASE_URL') and cfg.arm_config.get('WEBSERVER_PORT'):
        message += (f" Server URL: http://{cfg.arm_config['UI_BASE_URL']}:"
                    f"{cfg.arm_config['WEBSERVER_PORT']}")
    try:
        ripper_utils.notify(None, 'ARM notification', message)
    except Exception as err:  # pylint: disable=broad-except
        return api_error(f'Apprise test failed: {err}', 500, 'notify_error')
    return api_success(message='Test notification sent')
```

Add `settings_api` to the import list in `arm/ui/api/v1/__init__.py`.

- [ ] **Step 4: Run tests + commit**

```bash
wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui -v"
git add arm/ui/api/v1/settings_api.py arm/ui/api/v1/__init__.py test/unittest/ui/api/test_settings.py
git commit -m "feat(api): settings endpoints for arm.yaml/UI/abcde/apprise"
```

---

### Task 9: Drive endpoints — fix serialization, add scan/eject/remove/manual/update

**Files:**
- Modify: `arm/ui/api/v1/system.py` (fix `get_drives`, replace name-based eject, add five routes)
- Test: `test/unittest/ui/api/test_drives.py`

**Interfaces:**
- Consumes: `DriveUtils.get_drives() -> List[SystemDrives]`, `DriveUtils.drives_update() -> int`, `DriveUtils.job_cleanup(job_id)`, `SystemDrives` fields (`drive_id, name, description, mount, maker, model, serial, connection, read_cd, read_dvd, read_bd, drive_mode, stale, job_id_current, job_id_previous`), `drive.eject(method='toggle') -> error|None`, `drive.tray_status()`, `drive.open`.
- Produces: `serialize_drive(drive) -> dict`; routes `GET /system/drives` (fixed), `POST /system/drives/scan`, `POST /system/drives/<int:drive_id>/eject`, `DELETE /system/drives/<int:drive_id>`, `PUT /system/drives/<int:drive_id>`, `POST /system/drives/<int:drive_id>/manual`. The old broken `POST /system/drives/<drive_name>/eject` (by name) is removed.

- [ ] **Step 1: Write failing tests**

`test/unittest/ui/api/test_drives.py`:

```python
"""System drive endpoints."""
from unittest.mock import patch

from test.unittest.ui.api.base import ApiTestBase
from arm.models.system_drives import SystemDrives


def make_drive(**attrs):
    drive = SystemDrives.__new__(SystemDrives)
    defaults = {'drive_id': None, 'name': 'DRIVE-1', 'description': 'Main drive',
                'mount': '/dev/sr0', 'maker': 'LG', 'model': 'WH16NS60',
                'serial': 'SER123', 'connection': 'sata', 'read_cd': True,
                'read_dvd': True, 'read_bd': True, 'drive_mode': 'auto',
                'stale': False, 'job_id_current': None, 'job_id_previous': None}
    defaults.update(attrs)
    for key, value in defaults.items():
        setattr(drive, key, value)
    return drive


class TestDrives(ApiTestBase):

    def setUp(self):
        super().setUp()
        self.create_admin()
        self.token = self.get_token()
        self.drive = make_drive()
        from arm.ui import db
        db.session.add(self.drive)
        db.session.commit()

    def test_list_drives_serializes_real_fields(self):
        resp = self.client.get('/api/v1/system/drives', headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()['data']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['mount'], '/dev/sr0')
        self.assertEqual(data[0]['model'], 'WH16NS60')
        self.assertIn('drive_mode', data[0])

    def test_scan_drives(self):
        with patch('arm.ui.api.v1.system.drive_utils.drives_update',
                   return_value=2) as mocked:
            resp = self.client.post('/api/v1/system/drives/scan',
                                    headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()['data']['new_drives'], 2)
        mocked.assert_called_once()

    def test_eject_toggle(self):
        with patch.object(SystemDrives, 'eject', return_value=None) as mocked:
            resp = self.client.post(f'/api/v1/system/drives/{self.drive.drive_id}/eject',
                                    headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 200)
        mocked.assert_called_once()

    def test_eject_unknown_drive_404(self):
        resp = self.client.post('/api/v1/system/drives/999/eject',
                                headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 404)

    def test_remove_drive(self):
        drive_id = self.drive.drive_id
        resp = self.client.delete(f'/api/v1/system/drives/{drive_id}',
                                  headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(SystemDrives.query.filter_by(drive_id=drive_id).first())

    def test_update_drive_details(self):
        resp = self.client.put(f'/api/v1/system/drives/{self.drive.drive_id}',
                               headers=self.auth(self.token),
                               json={'name': 'BEDROOM', 'drive_mode': 'manual'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.drive.name, 'BEDROOM')
        self.assertEqual(self.drive.drive_mode, 'manual')

    def test_manual_rip_starts_process(self):
        with patch('arm.ui.api.v1.system.subprocess.Popen') as popen:
            popen.return_value.communicate.return_value = ('', '')
            popen.return_value.returncode = 0
            resp = self.client.post(
                f'/api/v1/system/drives/{self.drive.drive_id}/manual',
                headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 200)
        popen.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui/api/test_drives.py -v"`
Expected: FAIL (`/system/drives` 500s from nonexistent attributes; new routes 404).

- [ ] **Step 3: Implement in `system.py`**

Update imports at top of `arm/ui/api/v1/system.py`:

```python
"""API v1 System routes."""
import os
import subprocess

import psutil
from flask import current_app, request

import arm.config.config as cfg
from arm.models.system_info import SystemInfo
from arm.models.system_drives import SystemDrives
from arm.ui import db
from arm.ui.settings import DriveUtils as drive_utils
from arm.ui.settings.ServerUtil import ServerUtil
from arm.ui.settings.settings import check_hw_transcode_support

from . import api_v1
from .auth import require_token
from .helpers import api_error, api_success
```

Replace `get_drives` and the broken name-based `eject_drive`, and append the new routes:

```python
def serialize_drive(drive):
    """Serialize a SystemDrives row for the API."""
    return {
        'drive_id': drive.drive_id,
        'name': drive.name,
        'description': drive.description,
        'mount': drive.mount,
        'maker': drive.maker,
        'model': drive.model,
        'serial': drive.serial,
        'connection': drive.connection,
        'read_cd': drive.read_cd,
        'read_dvd': drive.read_dvd,
        'read_bd': drive.read_bd,
        'drive_mode': drive.drive_mode,
        'stale': drive.stale,
        'job_id_current': drive.job_id_current,
        'job_id_previous': drive.job_id_previous,
        'tray_open': getattr(drive, 'open', None),
    }


@api_v1.route('/system/drives', methods=['GET'])
@require_token
def get_drives():
    """List optical drives from the database."""
    try:
        drives = drive_utils.get_drives()
        return api_success(data=[serialize_drive(drive) for drive in drives])
    except Exception as err:  # pylint: disable=broad-except
        current_app.logger.error(f'Error getting drives: {err}')
        return api_error('Internal server error', 500, 'internal_error')


@api_v1.route('/system/drives/scan', methods=['POST'])
@require_token
def scan_drives():
    """Rescan the system for optical drives (mirrors legacy systemdrivescan)."""
    try:
        new_count = drive_utils.drives_update()
        return api_success(data={'new_drives': new_count},
                           message=f'ARM found {new_count} new drives')
    except Exception as err:  # pylint: disable=broad-except
        current_app.logger.error(f'Error scanning drives: {err}')
        return api_error('Internal server error', 500, 'internal_error')


@api_v1.route('/system/drives/<int:drive_id>/eject', methods=['POST'])
@require_token
def eject_drive(drive_id):
    """Toggle a drive tray (mirrors legacy drive_eject, by drive_id)."""
    try:
        drive = SystemDrives.query.filter_by(drive_id=drive_id).first()
        if not drive:
            return api_error(f'Drive {drive_id} not found', 404, 'not_found')
        if drive.job_id_current:
            drive.tray_status()
            if not drive.open:
                return api_error(
                    f'Job {drive.job_id_current} in progress. Cannot eject.',
                    409, 'job_in_progress')
        error = drive.eject(method='toggle')
        if error is not None:
            return api_error(str(error), 500, 'eject_error')
        return api_success(message=f'Drive {drive.name} tray toggled')
    except Exception as err:  # pylint: disable=broad-except
        current_app.logger.error(f'Error ejecting drive {drive_id}: {err}')
        return api_error('Internal server error', 500, 'internal_error')


@api_v1.route('/system/drives/<int:drive_id>', methods=['DELETE'])
@require_token
def remove_drive(drive_id):
    """Remove a drive from the ARM database (mirrors legacy drive_remove)."""
    try:
        drive = SystemDrives.query.filter_by(drive_id=drive_id).first()
        if not drive:
            return api_error(f'Drive {drive_id} not found', 404, 'not_found')
        dev_path = drive.mount
        SystemDrives.query.filter_by(drive_id=drive_id).delete()
        db.session.commit()
        current_app.logger.info(f'Removed drive [{dev_path}] from ARM')
        return api_success(message=f'Removed drive {dev_path} from ARM')
    except Exception as err:  # pylint: disable=broad-except
        current_app.logger.error(f'Drive removal encountered an error: {err}')
        return api_error('Drive unable to be removed', 500, 'internal_error')


@api_v1.route('/system/drives/<int:drive_id>', methods=['PUT'])
@require_token
def update_drive(drive_id):
    """Update drive name/description/mode (mirrors legacy systeminfo form)."""
    try:
        drive = SystemDrives.query.filter_by(drive_id=drive_id).first()
        if not drive:
            return api_error(f'Drive {drive_id} not found', 404, 'not_found')
        data = request.get_json(silent=True) or {}
        allowed = ('name', 'description', 'drive_mode')
        updated = [field for field in allowed if field in data]
        if not updated:
            return api_error('No valid fields to update', 400, 'validation_error')
        for field in updated:
            setattr(drive, field, str(data[field]).strip())
        db.session.commit()
        return api_success(data=serialize_drive(drive), message='Drive updated')
    except Exception as err:  # pylint: disable=broad-except
        current_app.logger.error(f'Error updating drive {drive_id}: {err}')
        return api_error('Internal server error', 500, 'internal_error')


@api_v1.route('/system/drives/<int:drive_id>/manual', methods=['POST'])
@require_token
def manual_rip_drive(drive_id):
    """Manually trigger an ARM job on a drive (mirrors legacy drive_manual)."""
    try:
        drive = SystemDrives.query.filter_by(drive_id=drive_id).first()
        if not drive:
            return api_error(f'Drive {drive_id} not found', 404, 'not_found')
        dev_path = drive.mount.lstrip('/dev/')
        cmd = os.path.join(
            cfg.arm_config['INSTALLPATH'],
            f'scripts/docker/docker_arm_wrapper.sh {dev_path}',
        )
        current_app.logger.debug(f'Running command [{cmd}]')
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        _, stderr = process.communicate()
        if process.returncode != 0:
            current_app.logger.error(f'Manual rip stderr: {stderr}')
            return api_error(
                f"Failed to start a job on drive '{drive.name}'. See logs.",
                500, 'process_error')
        return api_success(message=f"Manually starting a job on drive '{drive.name}'")
    except Exception as err:  # pylint: disable=broad-except
        current_app.logger.error(f'Error starting manual rip on {drive_id}: {err}')
        return api_error('Internal server error', 500, 'internal_error')
```

Delete the old name-based `eject_drive` route (it referenced attributes that do not exist on `SystemDrives`).

- [ ] **Step 4: Run tests + commit**

```bash
wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui -v && python3 -m flake8 arm/ui/api"
git add arm/ui/api/v1/system.py test/unittest/ui/api/test_drives.py
git commit -m "fix(api): serialize real SystemDrives fields; add scan/eject/remove/update/manual"
```

---

### Task 10: Notifications completion — timeout wiring + clear-all

**Files:**
- Modify: `arm/ui/api/v1/notifications.py`
- Test: `test/unittest/ui/api/test_notifications.py`

**Interfaces:**
- Consumes: `UISettings.notify_refresh` (ms, default 6500).
- Produces: `GET/PUT /api/v1/notifications/settings/timeout` (`timeout_ms`), `POST /api/v1/notifications/clear-all`, existing `GET /notifications` + `PUT /notifications/<id>/read` on the standard envelope.

- [ ] **Step 1: Write failing tests**

`test/unittest/ui/api/test_notifications.py`:

```python
"""Notification endpoints."""
from test.unittest.ui.api.base import ApiTestBase
from arm.models.ui_settings import UISettings


class TestNotifications(ApiTestBase):

    def setUp(self):
        super().setUp()
        self.create_admin()
        self.token = self.get_token()
        self.db.session.add(UISettings(use_icons=True, save_remote_images=False,
                                       bootstrap_skin='flatly', language='en',
                                       index_refresh=6500, database_limit=2500,
                                       notify_refresh=7500))
        self.db.session.commit()

    def test_list_unread_only(self):
        self.make_notification(title='unread')
        note = self.make_notification(title='read')
        note.seen = True
        self.db.session.commit()
        resp = self.client.get('/api/v1/notifications?unread_only=true',
                               headers=self.auth(self.token))
        titles = [item['title'] for item in resp.get_json()['data']]
        self.assertIn('unread', titles)
        self.assertNotIn('read', titles)

    def test_mark_read(self):
        note = self.make_notification()
        resp = self.client.put(f'/api/v1/notifications/{note.id}/read',
                               headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(note.seen)

    def test_mark_read_unknown_404(self):
        resp = self.client.put('/api/v1/notifications/999/read',
                               headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 404)

    def test_timeout_get_reads_ui_settings(self):
        resp = self.client.get('/api/v1/notifications/settings/timeout',
                               headers=self.auth(self.token))
        self.assertEqual(resp.get_json()['data']['timeout_ms'], 7500)

    def test_timeout_put_updates_ui_settings(self):
        resp = self.client.put('/api/v1/notifications/settings/timeout',
                               headers=self.auth(self.token),
                               json={'timeout_ms': 9000})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(UISettings.query.get(1).notify_refresh, 9000)

    def test_timeout_put_invalid_400(self):
        resp = self.client.put('/api/v1/notifications/settings/timeout',
                               headers=self.auth(self.token),
                               json={'timeout_ms': 'forever'})
        self.assertEqual(resp.status_code, 400)

    def test_clear_all(self):
        self.make_notification()
        self.make_notification()
        resp = self.client.post('/api/v1/notifications/clear-all',
                                headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 200)
        from arm.models.notifications import Notifications
        remaining = Notifications.query.filter_by(cleared=False).count()
        self.assertEqual(remaining, 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui/api/test_notifications.py -v"`
Expected: timeout/clear-all tests FAIL (timeout hardcoded 30; clear-all 405).

- [ ] **Step 3: Rewrite `notifications.py`**

```python
"""API v1 notifications routes."""
import datetime

from flask import current_app, request

from arm.models.notifications import Notifications
from arm.models.ui_settings import UISettings
from arm.ui import db

from . import api_v1
from .auth import require_token
from .helpers import api_error, api_success, pagination_meta, parse_pagination


@api_v1.route('/notifications', methods=['GET'])
@require_token
def get_notifications():
    """List notifications (optionally only unread)."""
    try:
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        pagination = parse_pagination()
        if pagination is None:
            return api_error('Invalid pagination parameters', 400, 'validation_error')
        page, per_page = pagination

        query = Notifications.query
        if unread_only:
            query = query.filter_by(seen=False)
        query = query.order_by(Notifications.trigger_time.desc())

        total = query.count()
        notes = (query.offset((page - 1) * per_page).limit(per_page).all())
        return api_success(data=[note.get_d() for note in notes],
                           meta=pagination_meta(total, page, per_page))
    except Exception as err:  # pylint: disable=broad-except
        current_app.logger.error(f'Error getting notifications: {err}')
        return api_error('Internal server error', 500, 'internal_error')


@api_v1.route('/notifications/<int:notification_id>/read', methods=['PUT'])
@require_token
def mark_notification_read(notification_id):
    """Mark one notification as seen."""
    try:
        notification = Notifications.query.get(notification_id)
        if not notification:
            return api_error(f'Notification {notification_id} not found',
                             404, 'not_found')
        notification.seen = True
        notification.dismiss_time = datetime.datetime.now()
        db.session.commit()
        return api_success(message='Notification marked as read')
    except Exception as err:  # pylint: disable=broad-except
        current_app.logger.error(
            f'Error marking notification {notification_id} as read: {err}')
        return api_error('Internal server error', 500, 'internal_error')


@api_v1.route('/notifications/clear-all', methods=['POST'])
@require_token
def clear_all_notifications():
    """Mark every notification as cleared."""
    try:
        now = datetime.datetime.now()
        cleared = Notifications.query.filter_by(cleared=False).update(
            {'cleared': True, 'cleared_time': now})
        db.session.commit()
        return api_success(message=f'{cleared} notifications cleared')
    except Exception as err:  # pylint: disable=broad-except
        current_app.logger.error(f'Error clearing notifications: {err}')
        return api_error('Internal server error', 500, 'internal_error')


@api_v1.route('/notifications/settings/timeout', methods=['GET'])
@require_token
def get_notification_timeout():
    """UI notification refresh interval in ms (UISettings.notify_refresh)."""
    ui_cfg = UISettings.query.get(1)
    timeout = ui_cfg.notify_refresh if ui_cfg else 6500
    return api_success(data={'timeout_ms': timeout})


@api_v1.route('/notifications/settings/timeout', methods=['PUT'])
@require_token
def update_notification_timeout():
    """Update the notification refresh interval in ms."""
    ui_cfg = UISettings.query.get(1)
    if not ui_cfg:
        return api_error('UI settings not found', 404, 'not_found')
    data = request.get_json(silent=True) or {}
    try:
        timeout = int(data.get('timeout_ms', 6500))
    except (TypeError, ValueError):
        return api_error('timeout_ms must be an integer', 400, 'validation_error')
    timeout = max(1000, timeout)
    ui_cfg.notify_refresh = timeout
    db.session.commit()
    return api_success(data={'timeout_ms': timeout},
                       message='Notification timeout updated')
```

- [ ] **Step 4: Run tests + commit**

```bash
wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui -v"
git add arm/ui/api/v1/notifications.py test/unittest/ui/api/test_notifications.py
git commit -m "feat(api): wire notification timeout to UISettings, add clear-all"
```

---

### Task 11: Database tools endpoints

**Files:**
- Create: `arm/ui/api/v1/database.py`
- Modify: `arm/ui/api/v1/__init__.py` (add `database` import)
- Test: `test/unittest/ui/api/test_database.py`

**Interfaces:**
- Consumes: `ui_utils.arm_db_migrate()`, `ui_utils.check_db_version(install_path, db_file)`, `ui_utils.generate_file_list(path)`, `ui_utils.import_movie_add(poster_image, imdb_id, matched, path)`, `arm.ui.metadata.get_omdb_poster(title, year)`.
- Produces: `GET /api/v1/database/jobs` (paginated all-jobs browse), `POST /api/v1/database/migrate` (`{"mode": "migrate"|"new"}`), `POST /api/v1/database/import` (scan `COMPLETED_PATH` for untracked movies).

- [ ] **Step 1: Write failing tests**

`test/unittest/ui/api/test_database.py`:

```python
"""Database tools endpoints."""
import os
from unittest.mock import patch

from test.unittest.ui.api.base import ApiTestBase


class TestDatabase(ApiTestBase):

    def setUp(self):
        super().setUp()
        self.create_admin()
        self.token = self.get_token()

    def test_browse_jobs(self):
        self.make_job(title='A')
        self.make_job(title='B')
        resp = self.client.get('/api/v1/database/jobs?per_page=1',
                               headers=self.auth(self.token))
        body = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body['meta']['total'], 2)
        self.assertEqual(len(body['data']), 1)

    def test_migrate_requires_valid_mode(self):
        resp = self.client.post('/api/v1/database/migrate',
                                headers=self.auth(self.token),
                                json={'mode': 'drop'})
        self.assertEqual(resp.status_code, 400)

    def test_migrate_calls_arm_db_migrate(self):
        with patch('arm.ui.api.v1.database.ui_utils.arm_db_migrate') as mocked:
            resp = self.client.post('/api/v1/database/migrate',
                                    headers=self.auth(self.token),
                                    json={'mode': 'migrate'})
        self.assertEqual(resp.status_code, 200)
        mocked.assert_called_once()

    def test_import_scans_completed_path(self, ):
        import arm.config.config as cfg
        import re
        matched = re.match(r"([\w\ \'\.\-\&\,]*?) \((\d{2,4})\)", "Coco (2017)")
        with patch('arm.ui.api.v1.database.ui_utils.generate_file_list',
                   return_value=['Coco (2017)']) as list_mocked, \
             patch('arm.ui.api.v1.database.get_omdb_poster',
                   return_value=('poster.jpg', 'tt2380307')) as poster_mocked, \
             patch('arm.ui.api.v1.database.ui_utils.import_movie_add',
                   return_value={'title': 'Coco'}) as add_mocked:
            resp = self.client.post('/api/v1/database/import',
                                    headers=self.auth(self.token))
        self.assertEqual(resp.status_code, 200)
        list_mocked.assert_called_once_with(cfg.arm_config['COMPLETED_PATH'])
        poster_mocked.assert_called_once_with('Coco', '2017')
        add_mocked.assert_called_once()
        self.assertEqual(add_mocked.call_args[0][2].group(1), 'Coco')
        self.assertIn('added', resp.get_json()['data'])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui/api/test_database.py -v"`
Expected: FAIL (404).

- [ ] **Step 3: Implement**

`arm/ui/api/v1/database.py`:

```python
"""API v1 database tools routes."""
import os
import re

from flask import current_app, request
from sqlalchemy.exc import SQLAlchemyError

import arm.config.config as cfg
import arm.ui.utils as ui_utils
from arm.models.job import Job
from arm.ui import db
from arm.ui.metadata import get_omdb_poster

from . import api_v1
from .auth import require_token
from .helpers import api_error, api_success, pagination_meta, parse_pagination

MOVIE_DIR_REGEX = r"([\w\ \'\.\-\&\,]*?) \((\d{2,4})\)"


@api_v1.route('/database/jobs', methods=['GET'])
@require_token
def browse_database():
    """Browse all jobs regardless of status (mirrors legacy /database page)."""
    try:
        pagination = parse_pagination()
        if pagination is None:
            return api_error('Invalid pagination parameters', 400, 'validation_error')
        page, per_page = pagination
        query = Job.query.order_by(Job.job_id.desc())
        total = query.count()
        jobs = query.offset((page - 1) * per_page).limit(per_page).all()
        return api_success(data=[job.get_d() for job in jobs],
                           meta=pagination_meta(total, page, per_page))
    except SQLAlchemyError as err:
        current_app.logger.error(f'Database error browsing jobs: {err}')
        return api_error('Database error', 500, 'database_error')


@api_v1.route('/database/migrate', methods=['POST'])
@require_token
def migrate_database():
    """Run a database fix (mirrors legacy /dbupdate). mode: migrate|new."""
    data = request.get_json(silent=True) or {}
    mode = data.get('mode')
    if mode not in ('migrate', 'new'):
        return api_error("mode must be 'migrate' or 'new'", 400, 'validation_error')
    try:
        if mode == 'migrate':
            ui_utils.arm_db_migrate()
            return api_success(message='ARM database migration successful')
        ui_utils.check_db_version(cfg.arm_config['INSTALLPATH'],
                                  cfg.arm_config['DBFILE'])
        return api_success(message='ARM database setup successful')
    except Exception as err:  # pylint: disable=broad-except
        current_app.logger.error(f'Database {mode} failed: {err}')
        return api_error(f'Database {mode} failed', 500, 'internal_error')


@api_v1.route('/database/import', methods=['POST'])
@require_token
def import_movies():
    """Scan COMPLETED_PATH for movies ARM has not tracked and add them.

    Slow + many metadata requests (mirrors legacy /import_movies).
    """
    try:
        my_path = cfg.arm_config['COMPLETED_PATH']
        results = {'added': {}, 'notfound': {}}
        index = 0
        for movie in ui_utils.generate_file_list(my_path):
            matched = re.match(MOVIE_DIR_REGEX, movie)
            if matched:
                poster_image, imdb_id = get_omdb_poster(matched.group(1),
                                                        matched.group(2))
                results['added'][str(index)] = ui_utils.import_movie_add(
                    poster_image, imdb_id, matched,
                    os.path.join(my_path, str(movie)))
            else:
                # Treat as a parent dir; import "Series (year)" subfolders
                sub_path = os.path.join(my_path, str(movie))
                for sub_movie in ui_utils.generate_file_list(sub_path):
                    sub_matched = re.match(MOVIE_DIR_REGEX, sub_movie)
                    if sub_matched:
                        poster_image, imdb_id = get_omdb_poster(
                            sub_matched.group(1), sub_matched.group(2))
                        results['added'][str(index)] = ui_utils.import_movie_add(
                            poster_image, imdb_id, sub_matched,
                            os.path.join(sub_path, str(sub_movie)))
                    else:
                        results['notfound'][str(index)] = str(sub_movie)
                    index += 1
            index += 1
        db.session.commit()
        return api_success(data=results)
    except Exception as err:  # pylint: disable=broad-except
        current_app.logger.error(f'Error importing movies: {err}')
        return api_error('Internal server error', 500, 'internal_error')
```

Add `database` to the import list in `arm/ui/api/v1/__init__.py`.

- [ ] **Step 4: Run tests + commit**

```bash
wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui -v"
git add arm/ui/api/v1/database.py arm/ui/api/v1/__init__.py test/unittest/ui/api/test_database.py
git commit -m "feat(api): database browse/migrate/import endpoints"
```

---

### Task 12: WebSockets — connect auth + live job watchdog

**Files:**
- Modify: `arm/ui/api/v1/websockets.py`
- Modify: `arm/runui.py`
- Test: `test/unittest/ui/api/test_websockets.py`

**Interfaces:**
- Consumes: `Token.validate_token(raw)`, `process_logfile(logfile, job, dict)`, `Job`, `socketio`, `app`, `db`, `cfg.arm_config['LOGPATH']`.
- Produces:
  - `collect_job_states(jobs) -> Dict[job_id, {'status','stage','progress'}]`
  - `diff_and_emit(previous: dict, current: dict) -> None` (emits `job_progress` / `job_status_change` / `job_completed`)
  - `start_job_watchdog(interval=5)` — spawns the background loop via `socketio.start_background_task`
  - Client connect auth: `io('/ws/jobs', {auth: {token: '<bearer>'}})`; server emits `connected {success}` and disconnects invalid tokens (unless `DISABLE_LOGIN`).

- [ ] **Step 1: Write failing tests**

`test/unittest/ui/api/test_websockets.py`:

```python
"""Websocket watchdog unit tests (pure functions, no live socket)."""
from unittest.mock import MagicMock, patch

from test.unittest.ui.api.base import ApiTestBase


def make_state_job(job_id, status, stage, progress):
    job = MagicMock()
    job.job_id = job_id
    job.status = status
    job.stage = stage
    job.progress = progress
    job.finished = status in ('success', 'fail')
    return job


class TestWatchdog(ApiTestBase):

    def test_collect_job_states_parses_active_jobs(self):
        job = make_state_job(1, 'ripping', 'stage1', None)
        job.logfile = 'movie.log'
        with patch('arm.ui.api.v1.websockets.process_logfile') as parse_mocked:
            states = __import__('arm.ui.api.v1.websockets', fromlist=['x']) \
                .collect_job_states([job])
        parse_mocked.assert_called_once()
        self.assertEqual(states[1]['status'], 'ripping')

    def test_collect_skips_finished_jobs(self):
        job = make_state_job(2, 'success', None, '100')
        job.logfile = 'movie.log'
        with patch('arm.ui.api.v1.websockets.process_logfile') as parse_mocked:
            from arm.ui.api.v1 import websockets
            states = websockets.collect_job_states([job])
        parse_mocked.assert_not_called()
        self.assertEqual(states[2]['status'], 'success')

    def test_diff_emits_progress_change(self):
        from arm.ui.api.v1 import websockets
        with patch.object(websockets, 'emit_job_progress') as progress_mocked, \
             patch.object(websockets, 'emit_job_status_change'):
            websockets.diff_and_emit(
                {1: {'status': 'ripping', 'stage': 'a', 'progress': '10'}},
                {1: {'status': 'ripping', 'stage': 'b', 'progress': '20'}})
        progress_mocked.assert_called_once()

    def test_diff_emits_status_change_and_completion(self):
        from arm.ui.api.v1 import websockets
        with patch.object(websockets, 'emit_job_status_change') as status_mocked, \
             patch.object(websockets, 'emit_job_completed') as done_mocked, \
             patch.object(websockets, 'emit_job_progress'):
            websockets.diff_and_emit(
                {1: {'status': 'ripping', 'stage': 'a', 'progress': '90'}},
                {1: {'status': 'success', 'stage': 'a', 'progress': '100'}})
        status_mocked.assert_called_once()
        done_mocked.assert_called_once()

    def test_diff_emits_for_new_job(self):
        from arm.ui.api.v1 import websockets
        with patch.object(websockets, 'emit_job_progress') as progress_mocked, \
             patch.object(websockets, 'emit_job_status_change') as status_mocked:
            websockets.diff_and_emit({}, {1: {'status': 'active', 'stage': None,
                                              'progress': None}})
        progress_mocked.assert_called_once()
        status_mocked.assert_called_once()

    def test_no_emit_when_unchanged(self):
        from arm.ui.api.v1 import websockets
        state = {1: {'status': 'ripping', 'stage': 'a', 'progress': '10'}}
        with patch.object(websockets, 'emit_job_progress') as progress_mocked, \
             patch.object(websockets, 'emit_job_status_change') as status_mocked:
            websockets.diff_and_emit(state, {1: dict(state[1])})
        progress_mocked.assert_not_called()
        status_mocked.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui/api/test_websockets.py -v"`
Expected: FAIL (functions missing).

- [ ] **Step 3: Implement in `websockets.py`**

Add to imports and replace `handle_connect`; add the watchdog functions at the bottom:

```python
"""WebSocket handlers for real-time updates."""
import os

from flask_socketio import disconnect, emit, join_room, leave_room

import arm.config.config as cfg
from arm.models.job import Job
from arm.models.token import Token
from arm.ui import app, db, socketio
from arm.ui.json_api import process_logfile


@socketio.on('connect', namespace='/ws/jobs')
def handle_connect(auth=None):
    """Authenticate clients via Bearer token; allow through when login disabled."""
    if cfg.arm_config.get('DISABLE_LOGIN'):
        emit('connected', {'success': True})
        return
    raw_token = None
    if isinstance(auth, dict):
        raw_token = auth.get('token')
    if not raw_token or not Token.validate_token(raw_token):
        emit('connected', {'success': False, 'error': 'Invalid or missing token'})
        disconnect()
        return
    emit('connected', {'success': True})
```

(keep `handle_disconnect`, subscribe/unsubscribe handlers, and the three `emit_*` helpers exactly as they are; remove the unused `print`-based logging by using `app.logger.debug`.)

Append:

```python
def collect_job_states(jobs):
    """Snapshot {job_id: {status, stage, progress}}; parse logs for active jobs."""
    states = {}
    for job in jobs:
        state = {'status': job.status,
                 'stage': getattr(job, 'stage', None),
                 'progress': getattr(job, 'progress', None)}
        if not job.finished:
            job_log = os.path.join(cfg.arm_config['LOGPATH'], str(job.logfile))
            process_logfile(job_log, job, state)
        states[job.job_id] = state
    return states


def diff_and_emit(previous, current):
    """Compare snapshots and emit websocket events for every change."""
    for job_id, state in current.items():
        prev = previous.get(job_id)
        if prev is None:
            emit_job_progress(job_id, state)
            emit_job_status_change(job_id, None, state.get('status'))
            continue
        if (state.get('progress') != prev.get('progress')
                or state.get('stage') != prev.get('stage')):
            emit_job_progress(job_id, state)
        if state.get('status') != prev.get('status'):
            emit_job_status_change(job_id, prev.get('status'), state.get('status'))
            if state.get('status') in ('success', 'fail'):
                emit_job_completed(job_id, state.get('status') == 'success')
    for job_id, prev in previous.items():
        if job_id not in current and prev.get('status') not in ('success', 'fail'):
            emit_job_completed(job_id, False, 'Job removed')


def start_job_watchdog(interval=5):
    """Background loop: poll unfinished jobs, emit diffs to websocket clients.

    The ripper runs as a separate process, so the UI process polls the
    database/logfiles (no message broker needed).
    """
    previous = {}

    def _loop():
        nonlocal previous
        while True:
            try:
                with app.app_context():
                    jobs = db.session.query(Job).filter(~Job.finished).all()
                    current = collect_job_states(jobs)
                    diff_and_emit(previous, current)
                    previous = current
                    db.session.remove()
            except Exception as err:  # pylint: disable=broad-except
                app.logger.error(f'Job watchdog error: {err}')
            socketio.sleep(interval)

    socketio.start_background_task(_loop)
    app.logger.info('Job watchdog started')
```

Delete the old `send_job_update` helper — `collect_job_states` + `diff_and_emit` replace it (nothing references it).

- [ ] **Step 4: Start the watchdog in `arm/runui.py`**

Replace the `try:` block at the bottom (lines 90-96) with:

```python
    try:
        # Check if WebSocket support is needed
        if hasattr(app, 'socketio'):
            app.logger.info("Starting ARM-UI with WebSocket support")
            from arm.ui.api.v1.websockets import start_job_watchdog
            start_job_watchdog()
            socketio.run(app, host=host, port=port, debug=False)
        else:
            serve(app, host=host, port=port, threads=40)
```

- [ ] **Step 5: Run tests + commit**

```bash
wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest/ui -v && python3 -m flake8 arm/ui/api arm/runui.py"
git add arm/ui/api/v1/websockets.py arm/runui.py test/unittest/ui/api/test_websockets.py
git commit -m "feat(api): authenticated websocket + job progress watchdog"
```

---

### Task 13: Vite dev proxy + API README update

**Files:**
- Modify: `arm-react/vite.config.ts`
- Modify: `arm/ui/api/v1/README.md`

**Interfaces:**
- Produces: SPA dev server proxying `/api` and `/socket.io` to Flask (default `http://localhost:8080`, overridable via `VITE_ARM_API_BASE`); README documents every endpoint from Tasks 2-12, the hashed-token note, and websocket auth.

- [ ] **Step 1: Add dev proxy**

Read `arm-react/vite.config.ts` first, then merge this block into the existing `defineConfig` (keep all existing keys; only add `server`):

```ts
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_ARM_API_BASE || 'http://localhost:8080',
        changeOrigin: true,
      },
      '/socket.io': {
        target: process.env.VITE_ARM_API_BASE || 'http://localhost:8080',
        changeOrigin: true,
        ws: true,
      },
    },
  },
```

- [ ] **Step 2: Update `arm/ui/api/v1/README.md`**

Append/adjust sections (keep existing endpoint docs, update changed behavior):

```markdown
## Authentication (changed)

Tokens are stored **SHA-256 hashed** server-side. The raw token is returned
only by `POST /auth/token` and `POST /auth/refresh` — store it client-side;
it cannot be recovered. Existing plaintext tokens from earlier builds are
invalidated.

## Error format (changed)

All errors now return:
`{"success": false, "error": {"code": "<machine_readable>", "message": "<human readable>"}}`

## New endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/metadata/search?title=&year=` | Provider search (auto-retries without year) |
| GET | `/metadata/details?imdb_id=` | Full metadata for one title |
| PUT | `/jobs/<id>/title` | Update title/year/type/imdb/poster |
| PUT | `/jobs/<id>/tracks` | Track selection for manual mode |
| PUT | `/jobs/<id>/params` | Change rip params (disctype/lengths/method/mainfeature) |
| GET | `/history?status=&search=&page=&per_page=` | Finished jobs |
| GET | `/logs` | List log files |
| GET | `/logs/<name>?lines=N` | Tail a log (default 200, max 2000) |
| GET/PUT | `/settings/ui` | UI settings |
| GET/PUT | `/settings/arm` | arm.yaml (secrets masked on GET) |
| GET/PUT | `/settings/abcde` | abcde.conf content |
| GET/PUT | `/settings/apprise` | apprise.yaml |
| POST | `/settings/apprise/test` | Send test notification |
| POST | `/system/drives/scan` | Rescan drives |
| POST | `/system/drives/<id>/eject` | Toggle tray (id-based, replaces name-based) |
| DELETE | `/system/drives/<id>` | Remove drive |
| PUT | `/system/drives/<id>` | Update name/description/mode |
| POST | `/system/drives/<id>/manual` | Manually start job |
| POST | `/notifications/clear-all` | Clear all notifications |
| GET/PUT | `/notifications/settings/timeout` | Notification refresh (ms) |
| GET | `/database/jobs` | Browse all jobs |
| POST | `/database/migrate` | `{"mode":"migrate"\|"new"}` |
| POST | `/database/import` | Import movies from COMPLETED_PATH |

## WebSockets (changed)

Connect with auth: `io('/ws/jobs', { auth: { token: '<bearer>' } })`.
The server validates the token on connect, then emits `connected`.
Events: `job_progress`, `job_status_change`, `job_completed` — driven by a
server-side watchdog polling active jobs every 5s.

## Dev proxy (SPA)

`arm-react/vite.config.ts` proxies `/api` and `/socket.io` to Flask
(`http://localhost:8080` by default, override with `VITE_ARM_API_BASE`).
```

- [ ] **Step 3: Commit**

```bash
git add arm-react/vite.config.ts arm/ui/api/v1/README.md
git commit -m "docs(api): document full-parity endpoints; add vite dev proxy"
```

---

### Task 14: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m pytest test/unittest -v"`
Expected: all pass (existing ripper tests + all new API tests).

- [ ] **Step 2: Lint**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && python3 -m flake8 arm test"`
Expected: no output (clean).

- [ ] **Step 3: App smoke test**

Run: `wsl -e bash -lc "cd /mnt/d/code/automatic-ripping-machine && timeout 5 python3 arm/runui.py; true"`
Expected: logs `Starting ARM-UI`, watchdog started, no tracebacks (exit from timeout is success).

- [ ] **Step 4: Fix anything found, then final commit**

```bash
git add -A
git commit -m "chore(api): final verification fixes"
```

(Skip if nothing to fix.)

---

## Self-Review Notes

- Spec coverage: every decision from `docs/superpowers/specs/2026-09-09-rest-api-design.md` maps to a task (parity endpoints → Tasks 4-11; websockets → Task 12; bearer/hash auth + CSRF/CORS/SECRET_KEY → Task 3; envelope → Task 2; deps cleanup → Task 3; vite proxy → Task 13; SPA serving from Flask intentionally out of scope).
- Type consistency: `api_success/api_error/parse_pagination/pagination_meta` signatures identical across tasks; `Token.issue` used only by `auth.py`; `serialize_drive` defined in Task 9 and used only there.
- Known risk flagged in tasks: `Config.__init__` signature in Task 5 tests (executor must verify and adapt construction); engine caching is why the harness never swaps DB URIs.
