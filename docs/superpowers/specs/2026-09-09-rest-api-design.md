# REST API Full Parity — Design Spec

Date: 2026-09-09
Branch: `feature/rest-api`
Status: Approved interactively (see decisions below)

## Goal

Complete the existing `/api/v1` REST API so it covers everything the legacy
Jinja2 UI can do, giving the new `arm-react` SPA (Vite + React 19 + TS + MUI)
a full backend to consume. The React app will eventually replace the Jinja
UI; until then the legacy UI must keep working unchanged.

## Decisions (from brainstorming session)

1. **Build on existing work** — extend the current `/api/v1` blueprint and its
   `{success, data, error, meta}` envelope; no framework rewrite (no
   flask-smorest/restx). The unused `arm/ui/api/v1/schemas.py` (imports
   `marshmallow`, which is not in requirements.txt) gets deleted.
2. **Full UI parity** scope: jobs, title/metadata selection, track selection,
   settings (arm.yaml / UI / abcde / apprise), history, logs, drive
   management, notifications, database tools.
3. **WebSockets** for live updates — the existing `/ws/jobs` namespace gets
   wired up via a UI-side watchdog (the ripper runs in a separate process, so
   the UI process polls the DB/log state and emits changes; no message broker
   needed).
4. **Bearer-token auth** for the SPA — tokens stored SHA-256-hashed in the DB
   (raw token shown once at creation); `/api/v1` exempted from CSRF (token
   auth, not cookie auth); `SECRET_KEY` from `ARM_SECRET_KEY` env with random
   fallback; CORS restricted to `/api/*` with origins from `ARM_CORS_ORIGINS`.
5. **Approach**: incremental extension + thin service reuse — new API modules
   call the same helpers the legacy routes use (`ui_utils.metadata_selector`,
   `fix_permissions`, `send_to_remote_db`, `DriveUtils`, `build_arm_cfg`, …).
   No duplicated business logic; legacy routes untouched.

## Architecture

```
arm/ui/api/v1/
├── __init__.py       # blueprint + JSON error handlers
├── helpers.py        # NEW: api_success/api_error/pagination helpers
├── auth.py           # fixed token flow (hashed storage)
├── jobs.py           # existing + actions fixed + title/tracks/params PUTs
├── metadata.py       # NEW: provider search/details
├── history.py        # NEW: finished-job listing
├── logs.py           # NEW: log list/tail
├── settings_api.py   # NEW: ui/arm/abcde/apprise settings + apprise test
├── database.py       # NEW: db browse/migrate/import
├── config.py         # existing (per-job Config snapshot in DB)
├── system.py         # existing + fixed drive serialization + drive actions
├── notifications.py  # existing + timeout wiring + clear-all
└── websockets.py     # auth on connect + job watchdog
```

Response contract: `200 {"success": true, "data": ..., "message"?, "meta"?}` /
`4xx/5xx {"success": false, "error": {"code", "message"}}`. All endpoints
require `Authorization: Bearer <token>` except `POST /api/v1/auth/token`.

## Testing

Plain-unittest-style tests run by pytest, mirroring existing repo style.
A harness (`test/unittest/ui/api/base.py`) boots the real Flask app with a
generated throwaway `ARM_CONFIG_FILE`, in-memory SQLite, and issues real
tokens. Tests require POSIX (`fcntl`/`pyudev` imports) — run under WSL,
Linux, or CI.

## Out of scope

- React pages themselves (only the Vite dev proxy config is touched)
- Serving the built SPA from Flask (future task, after React reaches parity)
- OpenAPI/Swagger generation
