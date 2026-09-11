# ARM API v1 Documentation

This document describes the new REST API v1 for Automatic Ripping Machine (ARM), designed for external applications to interact with ARM programmatically.

## Overview

The API v1 provides modern RESTful endpoints with:
- Bearer token authentication
- JSON responses with consistent structure
- WebSocket support for real-time updates
- Full CRUD operations for jobs, configuration, and notifications
- System information and control

## Authentication

All API endpoints require authentication using Bearer tokens.

### Getting a Token

```bash
POST /api/v1/auth/token
Content-Type: application/json

{
  "username": "admin@example.com",
  "password": "your_password",
  "expiry_hours": 24  // optional, defaults to 24
}
```

Response:
```json
{
  "success": true,
  "data": {
    "token": "abc123...",
    "expiry": "2026-04-28T12:00:00",
    "user_id": 1
  }
}
```

### Using Tokens

Include the token in the Authorization header:
```
Authorization: Bearer abc123...
```

### Refreshing Tokens

```bash
POST /api/v1/auth/refresh
Authorization: Bearer current_token
Content-Type: application/json

{
  "expiry_hours": 24  // optional
}
```

### Revoking Tokens

```bash
POST /api/v1/auth/revoke
Authorization: Bearer token_to_revoke
```

## Response Format

All responses follow this structure:

```json
{
  "success": true|false,
  "data": { ... } | [...],
  "error": "error message",  // only present if success=false
  "meta": { ... }  // pagination info, etc.
}
```

## Endpoints

### Jobs

#### List Jobs
```bash
GET /api/v1/jobs?status=active&search=movie&page=1&per_page=50
```

Parameters:
- `status`: `active`, `success`, `fail`, or omit for all
- `search`: Search in title fields
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 50)

#### Get Job Details
```bash
GET /api/v1/jobs/{job_id}
```

#### Get Job Logs
```bash
GET /api/v1/jobs/{job_id}/logs
```

#### Get Job Progress
```bash
GET /api/v1/jobs/{job_id}/progress
```

#### Job Actions
```bash
POST /api/v1/jobs/{job_id}/actions
Content-Type: application/json

{
  "action": "abandon" | "fixperms" | "send"
}
```

#### Delete Job
```bash
DELETE /api/v1/jobs/{job_id}
```

### Settings

arm.yaml is the source of truth for ripper settings; the old `/api/v1/config` endpoints were removed.

#### Get Settings
```bash
GET /api/v1/settings
```
Returns `{values, comments, read_only}` where `values` holds every arm.yaml key, `comments` maps keys to their arm.yaml comments and `read_only` flags a non-writable config file.

#### Update Settings
```bash
PUT /api/v1/settings
Content-Type: application/json

{
  "PREVENT_99": false,
  "ARM_NAME": "my-arm",
  ...
}
```
Keys must already exist in arm.yaml (unknown keys return 400); values are coerced to the current value's type (non-coercible values return 400). arm.yaml is rebuilt, hot-reloaded and the new values returned. Read-only file returns 409.

#### Get / Update UI Settings
```bash
GET /api/v1/settings/ui
PUT /api/v1/settings/ui
Content-Type: application/json

{
  "index_refresh": 2000,
  "use_icons": true,
  "save_remote_images": false,
  "bootstrap_skin": "bootstrap",
  "language": "en",
  "database_limit": 50,
  "notify_refresh": 10
}
```

#### Get / Update abcde Config
```bash
GET /api/v1/settings/abcde
PUT /api/v1/settings/abcde
Content-Type: application/json

{
  "content": "<full abcde.conf text>"
}
```
Returns `{content, read_only}`; Windows line endings are cleaned on save.

#### Get / Update Apprise Config
```bash
GET /api/v1/settings/apprise
PUT /api/v1/settings/apprise
Content-Type: application/json

{
  "content": "<full apprise.yaml text>"
}
```
Returns `{content, read_only}`; content must parse as a YAML mapping (invalid YAML returns 400).

#### Test Apprise Notification
```bash
POST /api/v1/settings/apprise/test
```
Sends a test notification and returns the message that was sent.

### System

#### Get System Info
```bash
GET /api/v1/system/info
```

#### Get Drives
```bash
GET /api/v1/system/drives
```

#### Eject Drive
```bash
POST /api/v1/system/drives/{drive_name}/eject
```

#### Get System Stats
```bash
GET /api/v1/system/stats
```

#### Get System Dashboard
Homepage-style snapshot: server name/description/CPU from `SystemInfo`, live CPU/memory/disk usage from `ServerUtil`, transcode/completed paths from config, and HandBrake hardware encode flags (`hw_support`). Runs HandBrake probing like the legacy UI; use sparingly or rely on client caching.

```bash
GET /api/v1/system/dashboard
```

### Notifications

#### List Notifications
```bash
GET /api/v1/notifications?unread_only=true&page=1&per_page=50
```

#### Mark as Read
```bash
PUT /api/v1/notifications/{id}/read
```

#### Get Timeout Setting
```bash
GET /api/v1/notifications/settings/timeout
```

## WebSocket Real-Time Updates

Connect to WebSocket namespace `/ws/jobs` for real-time updates.

### Events

- `job_progress`: Job progress updates
- `job_status_change`: Job status changes
- `job_completed`: Job completion

### Client Commands

```javascript
// Subscribe to specific job
socket.emit('subscribe_job', { job_id: 123 });

// Subscribe to all jobs
socket.emit('subscribe_all_jobs');

// Unsubscribe
socket.emit('unsubscribe_job', { job_id: 123 });
socket.emit('unsubscribe_all_jobs');
```

## Error Handling

- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `500`: Internal Server Error

Error responses include an `error` field with details.

## Migration from /json

The legacy `/json` endpoints remain available for backward compatibility. New external applications should use `/api/v1` endpoints.

## Rate Limiting

Rate limiting is not currently implemented but can be added in the future.

## Examples

See the test files and implementation for detailed examples of request/response formats.