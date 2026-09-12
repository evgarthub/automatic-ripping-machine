# React UI — Missing/Broken Features Plan

## Context

The legacy UI (Flask templates + jQuery, `arm/ui/*/templates`, `arm/ui/static/js/`) is being replaced by
the React SPA (`arm-react/`). The v1 REST API (`arm/ui/api/v1/`) covers most needs, but several legacy
features are missing from the React UI and a few have verified bugs. This document lists each gap,
its root cause, and the implementation plan (frontend and backend where needed).

Legends:
- **Legacy** — how the old jQuery UI implements it
- **React (current)** — state of `arm-react` today
- **Root cause** — verified in code where marked
- **Plan** — implementation steps

---

## 1. Notification popups are not shown / not implemented — DONE

### Legacy
- DB-backed `Notifications` rows are rendered as Bootstrap toasts in `#toastHolder`
  (`arm/ui/templates/nav.html`, `arm/ui/static/js/common.js` `addToast()`).
- `jobRefresh.js` polls `/json?mode=joblist`; the response carries unread `notes`
  (`arm/ui/jobs/jobs.py` `feed_json()` -> `json_api.get_notifications()`), and any toast not already
  in the DOM is shown.
- Auto-hide timeout comes from UISettings (`GET /json?mode=notify_timeout`, default ~6.5s);
  on hide the client calls `GET /json?mode=read_notification&notify_id=N` (marks `seen=1`).
- Nav bell shows unread count badge (`arm/ui/notifications/`).

### React (current)
- `NotificationsPage` exists (list, mark read, delete) and the API is complete:
  `GET /api/v1/notifications?unread_only=`, `PUT /notifications/:id/read`, `DELETE /notifications`,
  `GET/PUT /notifications/settings/timeout`.
- **No global toast/popup system.** `Snackbar` is copy-pasted locally into `SettingsPage.tsx` and
  `NotificationsPage.tsx` only; job mutations (abandon/delete/metadata) give no feedback at all.

### Plan

> **Status: implemented.** Global host in `arm-react/src/providers/ToastProvider.tsx` (+ `useToast.ts` hook,
> split into its own file for the `react-refresh/only-export-components` lint rule), mounted in `AppProviders.tsx`.
> Poll interval is a fixed 10s (not `notify_refresh`, which is only the auto-hide duration); uniform toast
> duration for all severities; unread badge on the AppBar in `MainLayout.tsx`; both local Snackbar copies
> replaced; abandon/delete/metadata mutations on `JobDetailPage` now toast on success and error.

1. Add a `ToastProvider` in `arm-react/src/providers/AppProviders.tsx`:
   - Global MUI `Snackbar` host (queue, dedupe by notification id, max visible stack).
   - Expose `notify(severity, message)` via context for one-off feedback (mutation success/error).
2. TanStack Query poll `GET /api/v1/notifications?unread_only=true`; refetch interval from
   `GET /api/v1/notifications/settings/timeout` (UISettings value).
3. Render a popup per unseen notification; on dismiss call `PUT /notifications/:id/read`.
4. Add unread-count badge to the AppBar in `MainLayout.tsx`.
5. Replace the two local Snackbar implementations with the provider.

### Acceptance
- Job completion/title-update notifications appear as popups automatically and disappear after the
  configured timeout; dismissed popups appear as read on the Notifications page; unread badge updates.

---

## 2. Missing "Title Search" (metadata lookup)

### Legacy
Flow in `arm/ui/jobs/jobs.py`:
1. `GET /titlesearch` — form (`TitleSearchForm`: title + year), prefilled from the job.
2. `GET /list_titles?title=&year=&job_id=` — `ui_utils.metadata_selector("search", title, year)`
   (retries without year if empty); renders poster-card grid (`list_titles.html`).
3. `GET /gettitle?imdbID=...&job_id=...` — `metadata_selector("get_details", ..., imdb_id)`;
   renders poster/plot (`showtitle.html`).
4. `GET /updatetitle` — saves `title/year/video_type/imdbID/poster` to both `job.*` and
   `job.*_manual`, sets `hasnicetitle=True`, creates a `Notifications` row.
5. `GET /customTitle` — manual override without lookup.

Provider selection: `metadata_selector()` (`arm/ui/utils.py`) switches on `METADATA_PROVIDER`
(`omdb` -> `arm/ui/metadata.py` `call_omdb_api`, `tmdb` -> `tmdb_search`/`tmdb_find`, results
normalized to the OMDB shape).

### React (current)
- Only manual metadata editing: `MetadataDialog` on `JobDetailPage` (`PUT /jobs/:id/metadata`).
- OMDB/TMDB keys exist only as pass-through settings in `SettingsPage`; no lookup UI or API.
- **No title-search endpoints in API v1.**

### Plan (backend + frontend)
Backend (`arm/ui/api/v1/jobs.py`, new routes; reuse `ui_utils.metadata_selector` and the legacy
`updatetitle` logic — factor it into a shared helper rather than duplicating):
1. `GET /api/v1/jobs/:job_id/titlesearch?title=&year=` — search results (drop `Type: game`,
   retry without year), normalized shape: `[{imdb_id, title, year, poster, type}]`.
2. `GET /api/v1/jobs/:job_id/titlesearch/details?imdb_id=` — details incl. plot, poster,
   background_url, video_type.
3. `POST /api/v1/jobs/:job_id/titlesearch` body `{imdb_id}` (or `{title, year}` for custom) —
   applies the update (same fields/flags as legacy `updatetitle`), creates a notification,
   returns the updated job.
4. Unit tests for the new routes (mirror `test/unittest/test_api_v1_*`).

Frontend (`arm-react`):
5. "Title Search" button on `JobDetailPage` (and entry point from metadata dialog):
   - Step 1: search form prefilled with job title/year.
   - Step 2: poster results grid -> select -> details preview (poster, plot, year).
   - Step 3: Apply -> `POST` -> invalidate `['jobs', id]`, show toast (feature 1).
6. New `jobsApi` methods + types; labels in `labels.ts`.

### Acceptance
- Searching a job title shows poster results; applying updates job metadata (and `_manual` fields),
  `hasnicetitle` flips, notification popup appears, job card/detail show the new title/poster.

---

## 3. Missing "Edit Settings" (per-title ripping settings)

### Legacy
- "Edit Settings" button per job card -> `GET /changeparams?config_id=<job_id>`
  (`arm/ui/jobs/jobs.py` `changeparams()`), renders `ChangeParamsForm`
  (`arm/ui/forms.py`): `RIPMETHOD` (mkv/backup), `DISCTYPE` (dvd/bluray/music/data),
  `MAINFEATURE` (bool), `MINLENGTH` (int), `MAXLENGTH` (int).
- Save: AJAX -> `json_api.change_job_params(config_id)` writes `job.disctype` and the per-job
  `Config` values, creates a `Notifications` row, returns success + timestamp.

### React (current)
- Global settings only (`SettingsPage`). `job.config` exists in `arm-react/src/api/types.ts`
  but is never rendered; no per-job params endpoint in API v1.

### Plan (backend + frontend)
Backend:
1. `GET /api/v1/jobs/:job_id/params` — returns the 5 editable values from `job.config` (+ disctype).
2. `PUT /api/v1/jobs/:job_id/params` — validate (ripmethod/disctype enums, ints for lengths,
   bool mainfeature), persist via the same logic as `json_api.change_job_params` (factor shared),
   create a notification, return updated values.
3. Unit tests.

Frontend:
4. "Edit Ripping Settings" button on `JobDetailPage` -> dialog with the 5 fields
   (selects/switch/number inputs, same constraints as `ChangeParamsForm`).
5. Save -> `PUT` -> invalidate `['jobs', id]` + toast (feature 1).
6. Note in dialog: only effective for jobs in `manual` mode waiting for start (same as legacy).

### Acceptance
- Editing RIPMETHOD/MINLENGTH/etc. for a waiting job changes ripper behaviour and the values
  persist after reload.

---

## 4. Log filtering broken — only `[HB]` tagged lines match, rest untagged

### Root cause (verified)
`arm-react/src/utils/logParser.ts:8`:

```ts
const TOOL_TAG_RE = /^\[(ARM|MKV|HB|FFMPEG|ABCDE)\]\s*(.*)/
```

The regex only matches tags at the **start of the line**. Actual log-file formats:

- ARM's own logger (`arm/ripper/logger.py:21`): `%(asctime)s ARM: %(levelname)s: %(message)s`
  -> e.g. `2026-09-11 12:00:00 ARM: INFO: Starting job...` — never matches `^\[ARM\]` -> untagged.
- MakeMKV debug lines go through the logging formatter (`makemkv.py` `logging.debug(f"[MKV] {line}")`)
  so the `[MKV]` tag ends up mid-line -> untagged.
- Only raw redirected tool output starts with a tag (`handbrake.py:58` `[HB]{line}`,
  `ffmpeg.py:505`, `makemkv.py:1198`, `utils.py:514`) -> matches. Hence "only handbrake tagged".

The tool-filter `ToggleButtonGroup` in `LogViewer.tsx` therefore shows mostly untagged lines.

### Plan (frontend only)
1. Rework `classifyToolTag()` in `logParser.ts`:
   - ARM: match `<timestamp> ARM: <LEVEL>: ...` (also covers old `ARM:`-only lines).
   - MKV/HB/FFMPEG/ABCDE: match the bracketed tag anywhere in the line, not only at start.
   - Everything else: explicit `other` category with its own color and filter chip.
2. Parse the log level (`DEBUG|INFO|WARNING|ERROR|CRITICAL`) from ARM lines into the segment
   model; add level filter chips (legacy UI never had this — improvement).
3. Add free-text search/highlight box to `LogViewer.tsx`.
4. Unit tests for the parser (add vitest if no runner exists yet — currently none in `arm-react`).

### Acceptance
- ARM/MKV/FFMPEG/ABCDE filters each show their lines; "All" shows everything; untagged lines are
  an explicit category; level filter and text search work.

---

## 5. Ripping progress not shown

### Root cause (verified) — socket namespace mismatch
- Server: all emits and handlers use namespace `/ws/jobs`
  (`arm/ui/api/v1/websockets.py:15-55`, `@socketio.on(..., namespace='/ws/jobs')`).
- Client: `arm-react/src/hooks/useArmSocket.ts:36` connects with `io({ path: '/socket.io', ... })`
  — the **default `/` namespace** — and emits `subscribe_all_jobs` / listens for `job_progress`
  there. No server handler or emit exists on `/`, so **no realtime event ever reaches the client**.

Secondary notes:
- REST fallback exists: `ActiveJobCard` polls `GET /jobs/:id/progress` every 15s, JobDetail 30s —
  but progress between polls is stale and `progress_round` is received and dropped.
- Verify during a live rip that `job.progress` is written to DB in the MakeMKV stage too
  (`arm/ripper/progress.py` `emit_job_progress`, throttled >=2s/>=5%), not only for HandBrake.

### Plan
1. Fix the client: `io({ path: '/socket.io', namespace: '/ws/jobs', ... })` (or alternatively emit
   on `/` server-side — pick one; client fix is the smaller diff and matches the API design).
2. Confirm `subscribe_all_jobs` payload matches the handler (`handle_subscribe_all_jobs`).
3. Store and render `progress_round` (percent label) from both socket and REST payloads.
4. Test during a real rip: Home cards and JobDetail update in near-realtime (poller runs at 2s);
   if MakeMKV-stage progress stays null, fix the ripper-side writer (backend).

### Acceptance
- During an active rip the progress bar, stage and ETA update without page refresh, at worst a
  few seconds behind; indeterminate bar only when progress is genuinely unknown.

---

## 6. Eject tray button opens only — legacy toggled open/close

### Root cause (verified)
- `arm/ui/api/v1/system.py:125` calls `drive.eject()` with the default `method="eject"`
  (open only). `SystemDrives.eject()` (`arm/models/system_drives.py:207`) supports
  `"close"` and `"toggle"`; the legacy route used `eject(method="toggle")`.
- The legacy route also has a job guard the API lacks: if `drive.job_id_current` is set and the
  tray is not open, eject is blocked with "Job [...] in progress. Cannot eject".

### Plan (backend + frontend)
Backend (`arm/ui/api/v1/system.py`):
1. Call `drive.eject(method="toggle")` (or accept an optional `method` in the request body,
   defaulting to `toggle`).
2. Add the job-in-progress guard (mirroring legacy `drive_eject()`).
3. Refresh and return the drive's new tray status in the response payload.

Frontend:
4. `DriveAdminTab` (`SettingsPage.tsx`): after eject, refresh tray state from the response
   (or invalidate the drives query) so the icon/chip reflects open vs closed.
5. Optional: show tray open/closed state on the drive row (legacy showed distinct icons) and add
   an eject button to the Home `DriveCard` (currently read-only, Settings-only).

### Acceptance
- Clicking eject on a closed empty drive opens it; clicking again closes it; blocked with a clear
  error when a job is running on that drive (unless tray already open).

---

## 7. `HB_PRESET_DVD` / `HB_PRESET_BD` should be dropdowns (presets from CLI or hardcoded)

### Current
- Both keys are rendered as free-text `TextField`s (generic `SettingsField` in
  `arm-react/src/pages/SettingsPage.tsx`; keys listed in the `handbrake` section, lines 161-162).
- The config comment itself hints at the source: `"Execute \"HandBrakeCLI -z\" to see a list of
  all presets"` (`arm/ui/comments.json:58`).
- Defaults (`setup/arm.yaml`): `HB_PRESET_DVD: "HQ 720p30 Surround"`,
  `HB_PRESET_BD: "HQ 1080p30 Surround"`.
- Note: the legacy UI also used a plain `StringField` (`arm/ui/forms.py:36`) — this is an
  improvement, not parity.

### Plan (backend + frontend)
Backend:
1. New endpoint `GET /api/v1/settings/handbrake/presets`:
   - Run `"{HANDBRAKE_LOCAL}" --preset-list` (a.k.a. `-z`; `HANDBRAKE_LOCAL` from arm.yaml —
     same binary the ripper uses, `arm/ripper/handbrake.py:319`), with a short timeout.
   - Parse the output: preset names from numbered lines after `+ Presets:` (strip ANSI escape
     codes; regex ~ `^\s*\d+\.\s+(.+)$`).
   - **Hardcoded fallback list** if the CLI is missing/fails/times out (e.g. `Fast 1080p30`,
     `Fast 720p30`, `Fast 480p30`, `HQ 1080p30 Surround`, `HQ 720p30 Surround`,
     `Very Fast 1080p30`, `Super HQ 1080p30 Surround`, `Super HQ 720p30 Surround`, plus the two
     ARM defaults above).
   - Include `source: "cli" | "fallback"` in the response so the UI can warn when values came
     from the fallback.
   - Cache in memory (presets are static per installation).
2. Unit tests with mocked CLI output (present/missing/failing binary).

Frontend:
3. `settingsApi.fetchHandbrakePresets()` + TanStack Query (long `staleTime`, presets are static).
4. In `RipperSettingsTab`, special-case `HB_PRESET_DVD` / `HB_PRESET_BD` to render a select
   (MUI `Autocomplete` with `freeSolo`, or `TextField select`) so:
   - options come from the presets query, always including the current value even when custom;
   - custom preset names remain valid (free text must still be allowed — custom/legacy names and
     user-defined presets exist);
   - dirty-tracking / save flow is unchanged (value stays a string).
5. Show a small hint when `source === "fallback"` (CLI unavailable — list may be incomplete).

### Acceptance
- Both preset fields are dropdowns populated from HandBrakeCLI; with the CLI unavailable they
  fall back to the hardcoded list with a visible hint; custom values can still be typed and saved;
  invalid names are still accepted by ARM as before (validation is HandBrake's job at rip time).

---

## 8. Noisy "fatal error" notifications for benign conditions (empty tray, duplicate run, SIGTERM)

Example spam: `"ARM encountered a fatal error during job setup. Check the logs for more details.
Timed out waiting for drive to be ready (ioctl tray status: CDS.TRAY_OPEN)."` — generated every
time the tray is open/closed with no disc.

### Root cause (verified)
1. udev rules trigger ARM on **every** `ACTION=="change"` block event
   (`setup/51-automedia.rules:7`) — including tray open/close, so `main.py` starts with no disc.
2. `setup()` waits 10s for the drive, then raises
   `RipperException("Timed out waiting for drive to be ready (ioctl tray status: CDS.TRAY_OPEN)")`
   (`arm/ripper/main.py:194`).
3. The top-level `__main__` handler treats **every** exception as fatal and always calls
   `utils.notify()` (`main.py:264-270`); `utils.notify` **always** creates a persistent
   `Notifications` DB row (`arm/ripper/utils.py:90-91`) and pushes to all remote channels
   (apprise/pushover/IFTTT/PushBullet/bash script).
4. Benign cases hitting this path:
   - empty tray / no disc at start (above);
   - `duplicate_run_check` -> `"Job already running on <dev>"` (`arm/ripper/utils.py:884`);
   - SIGTERM -> `"Received SIGTERM"` (`arm/ripper/main.py:168`).
5. Bonus bug: `main.py:271` (`job.status = JobState.FAILURE.value`) runs unguarded when
   `job is None`, raising `AttributeError` that masks the original exception in the
   setup-failure path (notify already fired by then, then the process crashes).
6. Interaction with feature #1: once toast popups ship, every benign event would also pop up in
   the UI — worth fixing before/with #1.

### Plan (backend only — `arm/ripper`)
1. Add a benign-exit exception, e.g. `RipperSkipException(RipperException)` in
   `arm/ripper/utils.py`, raised for expected/no-action conditions.
2. Raise it from:
   - the tray-not-ready timeout in `setup()` — and log at `info`/`warning`
     (`"No disc detected (tray status: <CDS.*>). Exiting."`) instead of `critical`;
   - `duplicate_run_check()` (`utils.py:884`);
   - the SIGTERM handler (`main.py:168`).
3. Top-level handler (`main.py:249-273`):
   - for `RipperSkipException`: log the reason and **skip `utils.notify` entirely**
     (no DB row, no remote push); exit without marking a failure;
   - keep the existing fatal-notify for genuine errors.
4. Guard the handler: only touch `job.status`/`job.errors` when `job` is not None
   (fixes the `AttributeError`, item 5 above).
5. Optional (only if users ask): a config gate (e.g. `NOTIFY_EMPTY_TRAY: false`) instead of
   hard-silencing, or a `DEBUG`-level notice so the event remains traceable in `arm.log`.
6. Unit tests: benign exception skips notify + does not crash with `job=None`; genuine errors
   still notify; `duplicate_run_check` and SIGTERM map to the benign class.

Out of scope / explicitly not changed: the udev rule itself (filtering `ENV{DISK_MEDIA_CHANGE}`
would also work but requires reinstalling rules on every host; the in-code fix is sufficient
and covers all trigger sources, e.g. manual `arm_wrapper.sh` runs).

### Acceptance
- Opening/closing an empty tray produces no notification (DB or remote) — only a log line.
- Double udev triggers and ARM shutdown (SIGTERM) produce no "fatal error" notification.
- Real failures (e.g. MakeMKV crash) still notify exactly as before.

---

## Suggested execution order

| # | Item | Size | Notes |
|---|------|------|-------|
| 1 | Eject toggle (#6) | S | Backend one-liner + guard + response state |
| 2 | Socket namespace fix (#5) | S | Client one-liner + `progress_round` rendering; live-rip verification |
| 3 | Log parser/filter fix (#4) | M | Frontend only; add parser tests |
| 4 | Global toast provider (#1) | M | DONE — ToastProvider + AppBar badge + mutation feedback |
| 5 | Per-title edit settings (#3) | M | Backend endpoints + dialog |
| 6 | Title search (#2) | L | Backend endpoints + multi-step dialog + tests |
| 7 | Preset dropdowns (#7) | M | Backend CLI endpoint + fallback + Autocomplete |
| 8 | Benign-error notify fix (#8) | S | Ripper only; do together with/before #1 |

Run `yarn lint`/`yarn build` (arm-react) and the Python unit tests for touched API modules after
each backend change.
