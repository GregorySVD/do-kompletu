# Do Kompletu

## Project overview

Do Kompletu helps people organize and discover real-world group activities, find
participants, and manage their own activities. This repository contains a FastAPI
API and a React web application with a map-based discovery view.

## Current status

The backend supports registration/login, profiles, canonical categories, activity
creation/discovery/details, persisted participation, My Activities, organizer
editing, soft cancellation, persistent participation, timed confirmation, and
geographic check-in for confirmed participants. PostgreSQL/PostGIS is authoritative
for proximity validation. Organizer-triggered attendance finalization records
terminal COMPLETED and NO_SHOW outcomes after activity end. FIFO waitlists now
queue full-activity requests and promote users atomically on active leave or
capacity increase before start. A lifespan worker now expires overdue reservations,
promotes FIFO waiters with late-confirmation grace, and expires remaining queues at start.
Public discovery excludes ended/cancelled activities, check-in requires a usable
client-reported GPS accuracy, `/ready` checks database connectivity, and production
startup validates the JWT secret. Refresh authentication errors remain 401 while
infrastructure failures follow the normal server-error path.

The backend also provides a private activity photo gallery: CHECKED_IN/COMPLETED
participants can upload up to three verified JPEG/PNG/WebP photos (10 MB each).
They and the organizer can view until strictly before `end_at + 72h`.
Images live in private S3-compatible storage; PostgreSQL stores metadata only.
See the [gallery contract](backend/docs/activity-gallery.md) and
[gallery milestone report](backend/docs/gallery-milestone-report.md).

Finalization now awards exactly **+10 points** for each new CHECKED_IN -> COMPLETED
transition. Attendance and the atomic `points_total` increment commit together;
retries do not award again. NO_SHOW, cancelled activities and organizing alone
award zero. There is no points ledger, level or rank system. See the
[points contract](backend/docs/activity-finalization.md#completion-points) and
[Real Points report](backend/docs/real-points-milestone-report.md).

Minimal administration now uses `User.is_admin`: protected user/activity lists,
account activation/deactivation, shared-service activity cancellation, and photo
moderation even after normal gallery closure. No general role system exists.
See the [administration contract](backend/docs/administration.md).
The backend MVP now enters **FEATURE FREEZE**.

Frontend authentication, profiles, discovery/details, creation, My Activities,
participant actions and organizer management already use real APIs. Admin UI and
gallery UI remain unimplemented. See
[Frontend integration status](#frontend-integration-status) for the verified gaps.

## Technology stack

| Area | Repository technology |
| --- | --- |
| Backend | Python 3.12 selected by `.python-version` (supported: 3.12–3.13), FastAPI, Pydantic/settings, SQLAlchemy 2, GeoAlchemy2, psycopg 3, Alembic |
| Authentication | JWT access/refresh tokens via python-jose; salted Argon2id password hashing via cryptography |
| Frontend | React 19, TypeScript 6, Vite 8, MUI 9, React Router, TanStack Query, Axios, React Hook Form/Zod, Day.js, Leaflet/react-leaflet |
| Database/infrastructure | PostgreSQL 17 + PostGIS 3.5 through Docker Compose; persistent named database volume |
| Development tools | uv and `backend/uv.lock`; pytest, Ruff; npm lockfile, ESLint, Prettier |

## Architecture overview

```text
backend/
  app/
    api/           HTTP routes and authentication dependencies
    core/          Settings, password hashing, JWT handling
    db/            SQLAlchemy sessions and base
    models/        User, Activity, ActivityParticipation, ActivityPhoto
    schemas/       Pydantic request/response and reference-data contracts
    services/      Authentication, profiles, activity and membership rules
    scripts/       Explicit development bootstrap-user command
  alembic/         Versioned database migrations
  docs/            Detailed backend contracts
  tests/           Isolated tests and gated PostgreSQL integration tests
  compose.yaml     PostgreSQL/PostGIS and local private MinIO
frontend/
  src/
    api/           Axios client and API functions
    context/       Authentication/session state
    hooks/         Queries, mutations, and view logic
    pages/         Routed screens
    components/    UI, map, and activity forms
    types/         TypeScript API/view types
    data/          Remaining My Activities fixtures
```

Requests pass through FastAPI validation/authentication, service rules, and
SQLAlchemy into PostgreSQL. Activity coordinates use PostGIS
`Geography(Point, 4326)` with a GiST index. Categories are canonical application
reference data, not a database category table. Fetch their IDs with
`GET /api/v1/categories`; Swagger's activity creation operation contains the
complete category UUID table and request examples.

### Concurrency and data integrity

Join, leave, confirm, check-in, edit, and cancel share an activity-row `SELECT ... FOR UPDATE` lock
under explicit PostgreSQL READ COMMITTED isolation. Writers refresh activity
state and check membership/time/capacity after acquiring that lock. This serializes
join vs join, join vs capacity reduction, join vs cancellation, concurrent
organizer updates, edit vs cancel, confirm vs leave/cancel, and confirm vs schedule
edit. Membership state is refreshed after waiting as well. The response snapshot is read before commit;
another transaction can change the activity afterward.

Membership uniqueness and foreign keys are database-enforced. Capacity and
lifecycle rules rely on cooperating service writers; direct SQL can bypass those
rules. Shared list/detail SQL projections derive counts and caller membership
without fetching every participant or issuing one query per activity. See the
[participation](backend/docs/activity-participation.md) and
[management](backend/docs/activity-management.md) contracts for transaction details.

## Implemented functionality

### Authentication and users

Registration stores a unique normalized email and a trimmed public `display_name`
(the username). Display-name comparisons for login and uniqueness are
case-insensitive, with original capitalization preserved. Application checks and
a PostgreSQL unique index on `lower(display_name)` enforce uniqueness. Passwords
are case-sensitive and hashed with Argon2id.

JSON login accepts an email or display name in **`identifier`**:

```http
POST /api/v1/auth/login
Content-Type: application/json

{"identifier": "username-or-email", "password": "your-password"}
```

The JSON key `email` is not accepted in place of `identifier`. Login returns an
access/refresh token pair. Refresh accepts `{"refresh_token":"<refresh-token>"}`
and returns a new access token. Invalid/expired tokens, wrong token types, and
unavailable users return 401; database or unexpected application failures are not
misclassified as authentication errors. Sample settings use 30-minute access and 7-day
refresh lifetimes. Protected endpoints accept
`Authorization: Bearer <access_token>`; refresh tokens cannot authorize them.
Swagger uses the separate OAuth2 form endpoint described below.

`GET /api/v1/users/me` returns the authenticated profile, including own-account
`is_active` and `is_admin`; PATCH updates
`display_name` and/or `avatar_url` (null clears the avatar). `points_total` is a
server-controlled aggregate balance: a newly finalized checked-in attendance adds
10 to the existing balance. Refetch `/users/me` to see awards made by an organizer;
profile requests cannot choose the balance or award amount.

### Activities and discovery

Creation accepts title/description, canonical `category_id`, start/end timestamps,
venue name/address, latitude/longitude, participant limits, and FREE/PAID pricing.
The organizer comes exclusively from the access JWT; client-supplied
`organizer_id` is rejected.

- Timestamps require a timezone offset, normalize to UTC, and require `end_at > start_at`.
  Creation currently permits past/ongoing dates; the frontend additionally rejects past starts.
- Coordinates use WGS 84: latitude −90 to 90, longitude −180 to 180.
- `min_participants` is 2–100. Limited activities require
  `has_participant_limit: true` and `max_participants` 2–100, at least the minimum.
  Unlimited activities use `has_participant_limit: false` and a null maximum.
- FREE requires null `price_amount`; PAID requires a positive PLN amount with at
  most two decimal places. This records pricing only; no payments are processed.

Public discovery returns an array of `ActivityListItem` cards/map items with real
membership counts. Filters are `query` (title, venue, address, category name/slug),
`category_id`, and `price_type`. Pagination uses `limit` (default 20, range 1–100)
and `offset` (default 0, minimum 0). Each list request uses one UTC-aware cutoff:
`cancelled_at IS NULL AND end_at > cutoff`. PUBLISHED and ONGOING activities are
included; CANCELLED and ENDED activities, including an exact `end_at == cutoff`,
are excluded. Lifecycle and requested filters run before ordering and pagination.
Existing start-time ascending and UUID ascending ordering is preserved for the
remaining records.

Detail returns `ActivityRead`, including safe public organizer identity, nullable
`cancelled_at`, caller membership, and action permissions. Authentication is
optional: absent credentials mean anonymous; supplied invalid/expired credentials
return 401. Only the caller's membership is exposed. Public discovery has no
personalized membership/permissions fields. Direct detail still returns ended and
cancelled activities, and My Activities/history retains its existing visibility.

### Participation

POST `/{activity_id}/join` creates membership (201); DELETE the same path leaves
(200). Both paths are under `/api/v1/activities`, require an access token, take no
body, and return updated `ActivityRead`.

- The organizer is separate from participants, cannot join/leave their own
  activity, and never consumes a participant place.
- One participation row persists per activity/user, with `status`, nullable `joined_at`, `waitlisted_at`,
  `left_at`, `confirmed_at`, `checked_in_at`, `completed_at`, and `no_show_at`.
  JOINED, CONFIRMED, and CHECKED_IN consume places; WAITLISTED, LEFT and final outcomes do not.
  `participant_count` counts only active rows; finite
  `available_slots` reflects remaining capacity, while unlimited capacity is null.
- Non-organizers may join/rejoin strictly before `start_at`; at/after start is
  409. Full limited activities succeed as WAITLISTED (201), without consuming a
  place. Leave remains allowed until `end_at`. Duplicate joins return 409,
  including queued duplicates; leaving without membership, including repeated DELETE, is 409.
- Leaving transitions JOINED/CONFIRMED to LEFT and sets `left_at`; the row,
  `joined_at`, and previous `confirmed_at` remain. Eligible rejoin reuses that row,
  selects JOINED or WAITLISTED from capacity and resets the appropriate cycle timestamps.
  CHECKED_IN cannot leave. Duplicate active-state joins remain 409. Ended and
  cancelled records remain persisted. Cancellation blocks join, leave, confirm, and check-in
  with 409, preserving that history. Organizer join/leave is always a 409 conflict.

`current_user_participation` is null for anonymous/non-member/LEFT callers, or
an object with status WAITLISTED, JOINED, CONFIRMED, CHECKED_IN, COMPLETED, or NO_SHOW for the
caller only. It includes joined_at and nullable confirmed_at, checked_in_at,
completed_at, and no_show_at. Final outcomes permit no participation mutations.
WAITLISTED adds waitlisted_at and 1-based waitlist_position, with joined_at=null.
Promotion preserves queue time and sets joined_at to promotion time; LEFT rejoin
starts a fresh active/queued cycle. waitlist_count is real. See the
[waitlist contract](backend/docs/activity-waitlist.md). The retained row captures the latest
cycle, not an immutable audit of every join/leave. See the
[full participation contract](backend/docs/activity-participation.md).

### Attendance confirmation and automatic lifecycle

POST `/api/v1/activities/{activity_id}/confirm` keeps its access JWT, no-body
request, and 200 ActivityRead response. Only JOINED may confirm. Default opening
is 60 minutes before start, inclusive; normal deadline is 30 minutes before start,
exclusive. Configure ACTIVITY_CONFIRMATION_OPEN_MINUTES_BEFORE and
ACTIVITY_CONFIRMATION_DEADLINE_MINUTES_BEFORE with open > deadline >= 0.
The old ACTIVITY_CONFIRMATION_WINDOW_HOURS setting has been removed.

A place acquired at/after the normal deadline gets
ACTIVITY_LATE_CONFIRMATION_GRACE_MINUTES (default 10), capped at start_at.
Earlier joins use the normal deadline. Top-level confirmation_deadline_at is
always the public normal deadline; the caller's JOINED object contains
`effective_confirmation_deadline_at`. Exact deadline rejects confirmation even
before a sweep updates an overdue JOINED row. Overdue JOINED cannot leave/rejoin
to bypass the deadline; voluntary LEFT before expiry keeps normal rejoin rules.

An in-process lifespan worker runs immediately and periodically, off the asyncio
event loop, with its own synchronous sessions. It atomically expires due JOINED
to terminal CONFIRMATION_EXPIRED, releases capacity, and promotes FIFO waiters
before start. At start it expires remaining WAITLISTED to WAITLIST_EXPIRED,
without promotion or NO_SHOW. Both states retain private timestamps, allow no
participant actions/rejoin, and are excluded from joined/waitlisted My Activities.
Cancellation skips automation and preserves its evidence. Explicit organizer
attendance finalization is unchanged and is never scheduled automatically.

PARTICIPATION_LIFECYCLE_WORKER_ENABLED defaults true; disable it explicitly for
tests or development if needed. PARTICIPATION_LIFECYCLE_SWEEP_INTERVAL_SECONDS
defaults 60 (finite, positive). The interval follows each completed sweep.
Multiple app processes serialize on existing activity-first PostgreSQL locks.
Persistence may lag deadlines until a sweep, while request-time eligibility is
always checked. No WebSockets/notifications are implemented; frontend refetch is
required. See the [worker contract](backend/docs/participation-lifecycle-worker.md)
for state, shutdown, migration, testability, and deployment details.

### Check-in

POST `/api/v1/activities/{activity_id}/check-in` requires an access token and JSON
`{"latitude":52.4232,"longitude":16.9461,"accuracy_m":20}`. All three fields are
required and finite; `accuracy_m` is a positive client-reported accuracy radius in
meters. Unknown fields are rejected. Only CONFIRMED non-organizers may
transition to CHECKED_IN (200); JOINED is not implicitly confirmed. Successful
check-in sets checked_in_at, preserves joined_at/confirmed_at, and consumes the
same existing place. Duplicate check-in, leave after check-in, and confirmation
after check-in return 409. There is no undo check-in.

The default window opens 30 minutes before start and closes at the earlier of
60 minutes after start or activity end: opening inclusive, deadline exclusive.
Configure `ACTIVITY_CHECK_IN_OPEN_MINUTES_BEFORE` and
`ACTIVITY_CHECK_IN_CLOSE_MINUTES_AFTER` (integers 0–525600), and
`ACTIVITY_CHECK_IN_RADIUS_METERS` (integer 1–100000, default 150).
`ACTIVITY_CHECK_IN_MAX_ACCURACY_METERS` defaults to 100 and must be finite and
positive. Accuracy equal to that limit is accepted; larger values return 409
`Location accuracy is insufficient for check-in` before the PostGIS radius query.
Existing public detail fields `checkin_opens_at`, `checkin_closes_at`, and
`checkin_radius_m` now carry this metadata.

PostgreSQL/PostGIS `ST_DWithin` checks the submitted point as `(longitude, latitude)`
against the stored activity geography, using meters and the spheroid. The allowed
radius is inclusive, subject to geospatial floating-point precision. Outside the
radius, wrong state, closed window, cancellation, or end returns 409. Invalid
coordinates, missing/nonpositive/nonfinite accuracy, or invalid bodies return 422.
`can_check_in` means state/time permit an attempt; POST must still validate accuracy
and proximity. No SQLite/Python fallback can authorize check-in.

Only checked_in_at is stored; submitted coordinates, accuracy, and computed distance
are neither persisted nor returned. Client-reported accuracy helps reject naturally
poor GPS fixes; it does not prove coordinates are genuine or prevent GPS spoofing.
PostGIS remains authoritative for the separate radius check. See the
[check-in contract](backend/docs/activity-check-in.md).

### Final attendance outcomes

POST `/api/v1/activities/{activity_id}/finalize` takes no body and requires the
organizer's access JWT. At `now >= end_at`, one atomic bulk update maps CHECKED_IN
to COMPLETED and JOINED/CONFIRMED to NO_SHOW. LEFT and existing final outcomes
remain unchanged. One UTC finalization time populates completed_at or no_show_at;
joined_at/confirmed_at/checked_in_at are preserved. Final states cannot be undone,
rejoined, left, confirmed, or checked in again.

The response is updated ActivityRead (200). Cancelled activities, requests before
end, and requests with no unresolved rows (including repeats and empty/LEFT-only
activities) return 409. `permissions.can_finalize` is true only for the organizer
of an ended uncancelled activity with unresolved attendance. All writers share the
activity-first row lock. The participation worker does not finalize attendance.

The Activity remains ENDED; COMPLETED is a participation state. The existing
`participant_count` remains an active capacity count and becomes zero after
finalization; finite available_slots therefore returns the full maximum, without
making an ended activity joinable. `checked_in_count` counts CHECKED_IN + COMPLETED
so verified check-ins survive finalization. No public completed/no-show analytics
or participant roster is added. Only rows that actually transition CHECKED_IN ->
COMPLETED earn +10 points, including participants deactivated after check-in.
Already-COMPLETED rows never earn again; cancelled activities cannot finalize or
award points. The organizer earns nothing merely for organizing. There is no
award-history ledger, backfill of historical COMPLETED rows, levels or reviews. See the
[finalization contract](backend/docs/activity-finalization.md).

### My Activities

`GET /api/v1/users/me/activities` requires an access token and scopes results to
that user; no client user ID is accepted.

| Parameter | Behavior |
| --- | --- |
| `relation` | Required: `organized` (caller owns activity), `waitlisted` (caller WAITLISTED only), or `joined` (current JOINED/CONFIRMED/CHECKED_IN before end; history also includes COMPLETED/NO_SHOW; LEFT and owned activities excluded) |
| `scope` | Optional: `upcoming` or `history`; omit for all times, including all organized activities |
| `limit`, `offset` | Default 20/0; limit 1–100, offset ≥ 0 |

One UTC cutoff drives filtering and serialization for the entire page. Upcoming
means `end_at > cutoff`, including ongoing activities, sorted by start then UUID
ascending. History means `end_at <= cutoff`, sorted by end descending then UUID
ascending. Omitted scope puts upcoming first, then history, using those same sorts.
Cancelled activities remain in all relations and use the same end-time scopes;
their status remains CANCELLED.
The Waitlist section uses `relation=waitlisted&scope=upcoming`; it may include
ongoing records because scopes still follow end time. Historical waitlists remain
until the next sweep persists expiry (cancelled records are skipped); joining and promotion close at start.

The response is an array of `ActivityRead`, with no total-count/page/`has_more`
wrapper. Unknown query parameters and literal `relation=all`/`scope=all` return
422. See the [My Activities contract](backend/docs/my-activities.md).

### Organizer editing and cancellation

PATCH `/api/v1/activities/{activity_id}` is an organizer-only partial update of
the public creation fields. Omitted fields stay unchanged; empty objects, unknown
fields, internal fields, and explicit nulls other than `max_participants` and
`price_amount` return 422. The merged activity is revalidated against creation
rules. Both the existing and proposed start must be strictly in the future:
ongoing, ended, or cancelled activities cannot be edited.

Capacity cannot be reduced below active membership (409), including CHECKED_IN;
WAITLISTED and LEFT do not count. Capacity increases promote earliest waiters into
new places in the same locked transaction before start. Switching to unlimited
promotes the entire queue. Actual changes to `start_at` or `end_at` return 409 while any participant
is CONFIRMED or CHECKED_IN. Once anyone is CHECKED_IN, latitude, longitude,
location_name, and address changes also return 409. Unchanged values and other allowed fields can still be submitted;
historical confirmations on LEFT rows do not block schedule edits. Confirmations
are never silently cleared by editing. Removing the limit
requires `{"has_participant_limit":false,"max_participants":null}`; switching
to FREE requires `{"price_type":"FREE","price_amount":null}`. Enabling a
limit or switching to PAID requires a consistent maximum or price. Omitted values
are not silently cleared.

POST `/api/v1/activities/{activity_id}/cancel` takes no body and allows the
organizer to cancel strictly before `end_at`, including ONGOING activities. It sets
`cancelled_at` once and returns 200 with `ActivityRead`. The activity and all
participation statuses/timestamps are preserved, including CHECKED_IN/checked_in_at;
counts still use all three active states,
excluding LEFT. Repeated cancellation and cancellation at/after
end return 409; another user's management attempt returns 403, and an unknown
activity returns 404. Invalid payloads return 422; missing/invalid access tokens
return 401. PATCH also returns 200 on success.

Cancelled activities disappear from public discovery but remain accessible by
direct detail and relevant My Activities queries. All action permissions become
false, and remaining slots no longer imply bookability. There is no hard deletion,
uncancel, cancellation reason, notification, or audit history. See the
[management/cancellation contract](backend/docs/activity-management.md).

## Activity lifecycle

Evaluate the first matching rule in this order:

| Priority | Condition | Status |
| --- | --- | --- |
| 1 | `cancelled_at` is set | `CANCELLED`, including after the planned end |
| 2 | Current UTC time ≥ `end_at` | `ENDED` |
| 3 | Current UTC time ≥ `start_at` | `ONGOING` |
| 4 | Otherwise | `PUBLISHED` |

Only `cancelled_at` is persisted as cancellation metadata. There is no arbitrary
mutable status column or DRAFT workflow. Cancellation is soft cancellation.
For uncancelled activities, organizers can edit before start and cancel before
end, and finalize unresolved attendance at/after end. Other users can join/leave
with join/rejoin restricted to before start and leave to before end; final outcomes
allow no attendance mutation. COMPLETED retains gallery access during its window.
`can_delete` (activity deletion) remains false; gallery view/upload permissions are real.

## API overview

All currently implemented application operations are listed below. “Access JWT”
also requires an active existing user. Interactive docs are at `/docs` and the
generated contract is at `/openapi.json`.

`GET /health` is lightweight process liveness and does not access the database.
`GET /ready` uses the normal database session to execute only `SELECT 1`:
200 `{"status":"ok"}` when reachable, or 503 `{"detail":"Database unavailable"}`
for recognized database connectivity/pool failures. It does not inspect schema or
PostGIS readiness. Connection details and exception text are not returned;
unexpected programming failures follow normal server-error handling.

| Method | Endpoint | Authentication | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | Public | API process liveness; does not check database readiness |
| GET | `/ready` | Public | PostgreSQL connectivity readiness via SELECT 1 |
| POST | `/api/v1/auth/register` | Public | Register an account |
| POST | `/api/v1/auth/login` | Identifier/password in JSON | Obtain access and refresh tokens |
| POST | `/api/v1/auth/token` | Username/password form | Swagger OAuth2 access token |
| POST | `/api/v1/auth/refresh` | Refresh JWT in JSON | Obtain a new access token |
| GET | `/api/v1/users/me` | Access JWT | Read own profile |
| PATCH | `/api/v1/users/me` | Access JWT | Update own display name/avatar |
| GET | `/api/v1/users/me/activities` | Access JWT | Organized/joined/waitlisted activities by scope |
| GET | `/api/v1/categories` | Public | Canonical category reference data |
| POST | `/api/v1/activities` | Access JWT | Create as authenticated organizer |
| GET | `/api/v1/activities` | Public | Filtered, paginated discovery excluding ENDED/CANCELLED |
| GET | `/api/v1/activities/{activity_id}` | Optional access JWT | Public detail plus caller state |
| PATCH | `/api/v1/activities/{activity_id}` | Organizer access JWT | Edit before existing start |
| POST | `/api/v1/activities/{activity_id}/cancel` | Organizer access JWT | Soft-cancel before end |
| POST | `/api/v1/activities/{activity_id}/finalize` | Organizer access JWT | Resolve attendance at/after end; uncancelled only |
| POST | `/api/v1/activities/{activity_id}/join` | Access JWT; non-organizer | Request JOINED or FIFO WAITLISTED |
| DELETE | `/api/v1/activities/{activity_id}/join` | Access JWT; non-organizer | Leave membership |
| POST | `/api/v1/activities/{activity_id}/confirm` | Access JWT; JOINED non-organizer | Confirm attendance inside the window |
| POST | `/api/v1/activities/{activity_id}/check-in` | Access JWT; CONFIRMED non-organizer | Time- and PostGIS-validated check-in |
| GET | `/api/v1/activities/{activity_id}/photos` | Eligible participant or organizer access JWT | Private gallery, ordered by created_at/id; presigned URLs |
| POST | `/api/v1/activities/{activity_id}/photos` | CHECKED_IN/COMPLETED access JWT | Multipart `file`, verified JPEG/PNG/WebP, max 10 MB, max 3/user/activity |
| DELETE | `/api/v1/activities/{activity_id}/photos/{photo_id}` | Eligible uploader or active admin access JWT | 204, storage first; admin may moderate after gallery closure |
| GET | `/api/v1/admin/users` | Active admin access JWT | Safe user list with email/account flags/points; limit/offset |
| PATCH | `/api/v1/admin/users/{user_id}/active` | Active admin access JWT | Activate/deactivate; self-deactivation returns 409 |
| GET | `/api/v1/admin/activities` | Active admin access JWT | Moderation projection including ended/cancelled activities; limit/offset |
| POST | `/api/v1/admin/activities/{activity_id}/cancel` | Active admin access JWT | Shared cancellation rules and lock without organizer ownership |

## Local development

### Requirements and environment

Install Docker with Compose, uv, and Python 3.12. Node/npm are needed only to run
the frontend. From the repository root, prepare the backend:

```powershell
cd backend
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv sync --frozen
```

On macOS/Linux, use `test -f .env || cp .env.example .env` for the copy step.
Edit your local `.env`, keeping it out of version control. The example contains:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/do_kompletu
JWT_SECRET=replace-me-with-a-long-random-secret
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
ACTIVITY_CONFIRMATION_OPEN_MINUTES_BEFORE=60
ACTIVITY_CONFIRMATION_DEADLINE_MINUTES_BEFORE=30
ACTIVITY_LATE_CONFIRMATION_GRACE_MINUTES=10
PARTICIPATION_LIFECYCLE_WORKER_ENABLED=true
PARTICIPATION_LIFECYCLE_SWEEP_INTERVAL_SECONDS=60
ACTIVITY_CHECK_IN_OPEN_MINUTES_BEFORE=30
ACTIVITY_CHECK_IN_CLOSE_MINUTES_AFTER=60
ACTIVITY_CHECK_IN_RADIUS_METERS=150
ACTIVITY_CHECK_IN_MAX_ACCURACY_METERS=100
```

Replace the JWT placeholder with a long random secret. Settings always load
`backend/.env`, independent of the launch directory. The CORS setting accepts
comma-separated origins or a JSON array.

With `ENVIRONMENT=production`, settings refuse startup for a missing/blank JWT
secret, recognized development/example placeholders, or fewer than 32 characters
after trimming whitespace. Configure a random non-default secret of at least that
length. Validation does not print the secret. Development/test keep their existing
local-secret conventions; this production rule adds no setup requirement there.

### Docker/PostgreSQL and migrations

Run from `backend/`:

```powershell
docker compose up -d --build
docker compose ps
uv run alembic upgrade head
uv run alembic current
```

Compose starts `database` (`postgis/postgis:17-3.5`) and development MinIO.
**Host port 5433 maps to container port 5432.** The development database is
`do_kompletu`; the example user/password are `postgres`/`postgres`. Data lives in
the named `do_kompletu_postgres_data` volume. Wait for its `pg_isready` healthcheck
to report healthy before migrating. Run the API separately; Compose does not
start it or apply migrations.

MinIO is built from the pinned community security release because maintained
community binary images are no longer published. The first build downloads Go
dependencies. S3 listens at `http://127.0.0.1:9000` and the local console at
`http://127.0.0.1:9001`; both bind only to loopback. Keep the six `S3_*` settings
and development-only `MINIO_ROOT_*` values from `.env.example` in local `.env`
(add them if your `.env` predates galleries). Once MinIO is healthy, run:

```powershell
uv run python -m app.scripts.init_photo_storage
```

This repeatable explicit command creates a private bucket if missing. API and
worker startup do not depend on object storage. Do not reuse local root credentials
for production; provision a private bucket and scoped credentials there.

The PostGIS image initializes the default database with PostGIS. Additional
manually created databases need `CREATE EXTENSION IF NOT EXISTS postgis;` before
the activities migration; revision `0003` assumes the extension already exists.
For example, for the Compose database:

```powershell
docker compose exec database psql -U postgres -d do_kompletu -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

### Start the API and frontend

From `backend/`, after migration:

```powershell
uv run fastapi dev app/main.py
```

API: <http://127.0.0.1:8000> · Swagger: <http://127.0.0.1:8000/docs> ·
OpenAPI: <http://127.0.0.1:8000/openapi.json>. No accounts or activities are seeded
automatically.

Optionally, in another PowerShell terminal from the repository root:

```powershell
cd frontend
npm ci
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
npm run dev
```

Open the Vite address (normally <http://localhost:5173>). Set the equivalent
environment variable in your shell on other platforms. `VITE_API_BASE_URL` is
read by the Axios client but is currently absent from `frontend/.env.example`;
that example only lists optional `VITE_CARTO_API_KEY`. Without a CARTO key the map
uses OpenStreetMap tiles. The frontend's own README is still a Vite template;
this root document describes the current project setup.

## Swagger / manual testing

1. Start the API and open <http://127.0.0.1:8000/docs>.
2. Register through `POST /api/v1/auth/register` with email, display_name, and a
   password of 8–128 characters, or run the bootstrap command below.
3. Select **Authorize**. Enter either email or display name in OAuth2 `username`.
   Enter the exact case-sensitive password; leave `client_id` and `client_secret`
   blank. Swagger posts form data to `/api/v1/auth/token` and stores the access token.
4. Read `/api/v1/users/me`, then fetch categories. Create an activity using a
   selectable Swagger request example with future timezone-aware dates. Copy the
   returned activity UUID; do not provide an organizer ID.
5. As organizer, PATCH the title and inspect `relation=organized` in My Activities.
6. Register a second account, log out in **Authorize**, and authorize as that user.
   Join the activity, read detail and `relation=joined&scope=upcoming`, leave, and
   rejoin. Check real counts and caller-specific permissions at each step. For
   confirmation testing, create the activity 30–60 minutes ahead and call
   `/confirm`; check CONFIRMED/confirmed_at and that schedule changes now return 409.
   For check-in, create within 30 minutes of start, confirm first, and POST your
   coordinates and positive `accuracy_m` no greater than the configured maximum to
   `/check-in`. Check CHECKED_IN/checked_in_at, checked_in_count,
   blocked leave, and protected location edits. Swagger examples use an illustrative
   venue; submitted coordinates must be within the actual activity's radius.
7. Reauthorize as organizer and cancel. Verify discovery omits the activity,
   direct detail shows CANCELLED, and both users' relevant My Activities lists
   retain it. Repeated cancel, or participant join/leave/confirm/check-in after cancel, returns 409.
8. For a separate uncancelled activity, wait until its end and authorize as the
   organizer to POST `/finalize`. Verify ENDED, participant_count=0, preserved
   checked_in_count, and can_finalize=false. Each participant's own detail/history
   should show COMPLETED if checked in, otherwise NO_SHOW. A repeat returns 409;
   the cancelled activity also rejects finalization without rewriting evidence.

Executing JSON `/auth/login` alone does not authorize Swagger's other operations;
use **Authorize** for that. JSON login uses `identifier`, whereas the OAuth2 form
uses `username`. The token form returns only an access token; JSON login returns
both access and refresh tokens. Obtain a fresh token when Swagger's access token
expires. Full error examples and contract details are in Swagger and the linked docs.

## Bootstrap development user

After migration, optionally set all three values in local `backend/.env`:

```dotenv
BOOTSTRAP_USER_EMAIL=developer@example.com
BOOTSTRAP_USER_DISPLAY_NAME=LocalDeveloper
BOOTSTRAP_USER_PASSWORD=replace-with-your-local-password
```

Run explicitly from `backend/`:

```powershell
uv run python -m app.scripts.create_bootstrap_user
```

This local development utility uses normal validation/hashing, requires all three
settings, and is disabled for `ENVIRONMENT=production`. It is idempotent for the
same email/display-name account and leaves its password unchanged. Conflicting
identifiers fail rather than overwrite another account. It creates an ordinary
user, not an administrator, and never runs automatically on startup. Keep actual
credentials in the ignored `.env`; never commit them.

Admin provisioning is a separate explicit local SQL step using an exact account
UUID; see [Local admin provisioning](backend/docs/administration.md#local-admin-provisioning-and-migration).
There is no auto-promoted first user, hardcoded admin email or public privilege API.

## Testing

Run from `backend/`:

```powershell
uv run pytest -v
uv run ruff check .
uv run python -m compileall app
uv lock --check
uv run alembic current
```

The default suite uses isolated SQLite fixtures and skips PostgreSQL integration
modules unless **`POSTGRES_TEST_DATABASE_URL`** is set in the shell. SQLite checks
functional contracts; it does not prove PostGIS behavior or PostgreSQL locking.
Integration tests require a running PostGIS-enabled database migrated to head.
For the repository's local Compose development database:

```powershell
$env:POSTGRES_TEST_DATABASE_URL = 'postgresql+psycopg://postgres:postgres@localhost:5433/do_kompletu'
$postgresTests = @(rg --files tests -g '*postgres.py')
uv run pytest -v @postgresTests
Remove-Item Env:POSTGRES_TEST_DATABASE_URL
```

Tests use rollback fixtures or commit only generated test records with targeted
cleanup for multi-connection races. They test PostGIS persistence/updates, schema
constraints, timestamps, ordering, counts/privacy, query counts, and actual row
lock contention. Use a local development/test database. Coverage includes auth,
bootstrap, categories, creation/discovery/detail, participation, My Activities,
management/cancellation, and OpenAPI contracts.
The lifecycle migration test creates/drops only a generated temporary database;
its database account needs CREATEDB permission and permission to install PostGIS.
The lifecycle, check-in, and finalization migration tests exercise
`0005 → 0006 → 0005 → 0006`, `0006 → 0007 → 0006 → 0007`, and
`0007 → 0008 → 0007 → 0008`; none downgrades the normal database. Isolated
check-in tests stub proximity explicitly; only real PostGIS tests validate geography.

Verified on 2026-10-31 for Minimal Admin. Actual pre-change baseline:
701 default tests passed (167 skipped) and 166 PostgreSQL/PostGIS tests passed.

| Check | Current result |
| --- | --- |
| Default `uv run pytest -v` without integration URLs | 760 passed, 177 skipped (176 PostgreSQL, 1 optional MinIO) |
| Separate full PostgreSQL/PostGIS suite in an isolated test database | 176 passed |
| Dedicated isolated admin module | 59 passed |
| Dedicated PostgreSQL admin and migration modules | 10 passed |
| Gallery/storage regression modules | 68 passed, 1 optional MinIO test skipped |
| Real MinIO smoke test | Not rerun for Minimal Admin; fake-storage and SDK tests passed |
| Ruff, compileall, `uv lock --check` | Passed |
| Source/test database head | `20261031_0012` |
| Development database | Remains at `20261030_0011`; data unchanged; run `uv run alembic upgrade head` before running the updated API |
| Admin migration cycle on a generated temporary database | `0011 -> 0012 -> 0011 -> 0012` passed, preserving existing users/activities/participations/photos |
| Historical gallery/waitlist/lifecycle/check-in/finalization migration cycles | Passed on generated temporary databases |
| `git diff --check` | Passed |
| `git diff -- frontend` | Empty |

The [42-point Minimal Admin report](backend/docs/minimal-admin-milestone-report.md)
records the final implementation, files, validation and frontend work. Earlier
milestone reports retain their historical verification results.

The tests report an existing Starlette TestClient/httpx deprecation warning and
local pytest-cache permission warnings. Git may also report an unreadable root
`.pytest_cache/` directory and LF/CRLF notices; these do not change the test results.
The temporary-database migration test also reports the existing Alembic
path_separator configuration deprecation; no warnings were suppressed.

## Database migrations

The verified linear chain and current head are:

| Revision | Exact filename under `backend/alembic/versions/` | Change |
| --- | --- | --- |
| `20260830_0001` | `20260830_0001_create_users_table.py` | Users and unique email |
| `20260927_0002` | `20260927_0002_add_case_insensitive_display_name_unique_index.py` | Case-insensitive display-name uniqueness |
| `20260927_0003` | `20260927_0003_create_activities_table.py` | Activities, PostGIS geography column/index, validation constraints |
| `20261018_0004` | `20261018_0004_create_activity_participations.py` | Unique user/activity memberships, FKs, joined_at, user index |
| `20261018_0005` | `20261018_0005_add_activity_cancellation.py` | Nullable activity cancelled_at |
| `20261018_0006` | `20261018_0006_add_participation_lifecycle.py` | Backfilled JOINED status, left_at/confirmed_at, lifecycle CHECK constraints |
| `20261018_0007` | `20261018_0007_add_participation_check_in.py` | Nullable checked_in_at, CHECKED_IN status and updated timestamp CHECKs |
| `20261018_0008` | `20261018_0008_add_final_attendance_outcomes.py` | Nullable completed_at/no_show_at, terminal COMPLETED/NO_SHOW and consistent timestamp CHECKs |
| `20261018_0009` | `20261018_0009_add_activity_waitlist.py` | WAITLISTED, waitlisted_at, nullable joined_at with state CHECKs, FIFO index |
| `20261019_0010` | `20261019_0010_add_participation_expiry.py` | System expiry states/timestamps, status VARCHAR(24), strict CHECKs |
| `20261030_0011` | `20261030_0011_create_activity_photos.py` | Private photo metadata, FK/size/MIME constraints and indexes |
| `20261031_0012` | `20261031_0012_add_user_is_admin.py` | NOT NULL admin boolean with retained false server default; **current head** |

Check file history with `uv run alembic history` and file heads with
`uv run alembic heads`. `uv run alembic current` checks the configured database.
Migration `0005` is additive and preserves activities/memberships. Its downgrade
discards cancellation metadata. `0006` backfills existing rows as JOINED, preserving
joined_at with null new timestamps. Its downgrade deletes LEFT rows to avoid
reactivating them in the old row-existence model, retains active rows, and loses
confirmation/lifecycle metadata. `0004` downgrade removes memberships.
Check-in migration 0007 preserves existing states; its downgrade maps CHECKED_IN
back to CONFIRMED, drops checked_in_at, and retains every participation row.
Finalization migration 0008 preserves all old states/timestamps. Downgrade maps
COMPLETED to CHECKED_IN, and NO_SHOW to CONFIRMED only if confirmed_at exists,
otherwise JOINED. It drops only finalization timestamps, retains every row, and
never fabricates confirmation evidence to satisfy the old constraint.
Waitlist migration 0009 preserves existing data and adds queue timestamps, nullable
joined_at with status CHECKs, and the FIFO index. Downgrade retains WAITLISTED as
inactive LEFT and uses queue-entry time for legacy mandatory joined_at on never-
joined rows; it loses queue history. See the waitlist contract for this compromise.
Historical upgrade/downgrade probes are recorded in the contracts; normal onboarding uses
`upgrade head`.

## Backend documentation

- [Administration contract](backend/docs/administration.md): simple boolean admin model, four endpoints, deactivation, shared cancellation, gallery moderation, provisioning and exact frontend work.
- [Minimal Admin milestone report](backend/docs/minimal-admin-milestone-report.md): all 42 requested review points and actual validation.
- [Real Points milestone report](backend/docs/real-points-milestone-report.md): 35 requested review points, actual validation and precise frontend follow-up.
- [Private activity gallery](backend/docs/activity-gallery.md): eligibility, expiry,
  image validation, object storage, MinIO, transactional quota, compensation and frontend contract.
- [Gallery milestone report](backend/docs/gallery-milestone-report.md): all 50 requested review points and actual validation results.
- [Activity participation contract](backend/docs/activity-participation.md):
  retained lifecycle, join/leave/rejoin/confirm, timing, full responses, privacy, and concurrency.
- [Automated lifecycle worker](backend/docs/participation-lifecycle-worker.md): confirmation/grace, expiry, worker startup/shutdown, locking and frontend polling.
- [FIFO waitlist contract](backend/docs/activity-waitlist.md): admission, queue timestamps/position, atomic promotion, migration/downgrade, frontend follow-up.
- [My Activities contract](backend/docs/my-activities.md): relation/scope semantics,
  sorting/pagination, full responses, query strategy, and frontend integration.
- [Activity management/cancellation contract](backend/docs/activity-management.md):
  partial editing, cancellation visibility/permissions, locks, errors, and migration validation.
- [Activity check-in contract](backend/docs/activity-check-in.md): time/proximity
  rules, PostGIS, privacy, leave/edit restrictions, and check-in migration validation.
- [Activity finalization contract](backend/docs/activity-finalization.md): terminal
  attendance, organizer endpoint, counts/history, migration cycle, and lock races.

These are the detailed contracts. Their earlier milestone verification tables
are explicitly historical; the current combined verification is listed above.

## Frontend integration status

Verified against the current source during Minimal Admin; no frontend files changed.
Older milestone reports describe their historical frontend state.

| Area | Current implementation | Remaining integration |
| --- | --- | --- |
| Authentication | JSON login, session restore, single-flight access refresh on 401, handling stale sessions/transient restore failures | Add `is_admin` to UserProfile and read it from the existing current-user response |
| Profile | Real profile read/edit and points display | Refetch the server balance when another user finalizes attendance |
| Discovery/details | Real categories, list/detail APIs and identity-scoped detail keys | Server filtering/pagination beyond the first 100 discovery results |
| Participation | Real join/leave/confirm/check-in API functions, mutation hooks and controls; GPS position/accuracy handling | No admin-specific change needed |
| My Activities | Real organized/joined/waitlisted/history queries and lifecycle rendering | No admin-specific change needed |
| Organizer management | Real editing/cancellation/finalization, confirmation dialogs and mutation invalidation | Admin cancellation must use its separate admin endpoint |
| Administration | No admin type, routes, guard, API module, tables or controls | Typed paginated lists, admin guard/navigation, user active toggle, activity cancel and photo deletion by known IDs |
| Gallery | Permission booleans and eligible participation types exist; no photo client/UI | Ordinary gallery UI and admin photo-moderation control; admin state grants no GET permission |
| Private caching | AuthContext clears My Activities and authenticated detail queries on account changes | Include future admin/gallery query keys in private-cache cleanup |

The exact admin frontend work is listed in
[administration](backend/docs/administration.md#frontend-integration-remaining).
Use the existing Axios client and query/mutation patterns. Handle 401, 403, 404,
409, 422 and storage 503 responses, disable self-deactivation, and invalidate
admin lists/detail/discovery/personal data after mutations. The normal app works
without an admin UI. No new backend endpoints are needed for this UI milestone.

## Current limitations / not implemented yet

- Scheduled/automatic finalization, organizer manual attendance overrides,
  undo completion/no-show, and separate cancelled-event attendance/refund policy.
- Reviews, ratings, a points ledger/history, levels, ranks, and achievements.
- Notifications, chat, frontend gallery integration, and automated media cleanup.
- Cancellation reasons, uncancel, activity edit history/audit trail, hard deletion,
  and DRAFT publishing workflows. Concurrent writes to the same field use the
  last successful writer; there is no version/conflict token.
- Payment/refund processing; PAID is descriptive pricing metadata only.
- Nearby radius/distance search and distance calculation; storing coordinates does
  not implement these features. Admin authorization uses a simple boolean;
  general RBAC, audit logs and richer moderation are outside the frozen MVP.

Placeholder fields do not imply implemented features: `tags` is empty,
`distance_m` is null, and activity-deletion permission remains false.
Gallery view/upload permissions, check-in timing/radius and checked_in_count are real.
My Activities has no total-count wrapper or cross-page snapshot guarantee.
There is no unconfirm, undo check-in, immutable participation event
log, or schedule-edit notification. Confirmation is a self-declared intent to attend.

## Feature freeze

The backend MVP is in **FEATURE FREEZE** after Minimal Admin. Completed scope
includes authentication/profiles, activities/discovery, participation/FIFO waitlists,
confirmation/expiry worker, PostGIS check-in, attendance finalization/completion
points, My Activities, private gallery, hardening and minimal administration.

Frontend admin/gallery integration and fixes can proceed against these contracts.
Reviews, rankings, achievements, notifications, chat, friends, payments, richer
moderation, audit logs and RBAC remain deferred and outside this MVP. No new MVP
backend features are proposed.

## Security / development notes

Keep `.env`, real passwords, JWT secrets, and tokens out of commits and logs. The
Compose credentials and example JWT value are for local setup; configure actual
deployment secrets and allowed CORS origins explicitly. Vite `VITE_*` values are
browser-visible and must not hold private secrets.

Protected endpoints validate token type/expiry and active-user identity. Organizer
ownership is checked server-side; frontend permissions guide UI and do not replace
authorization. Public organizer projections expose only ID, display name, and
avatar, never email/password hashes. Personalized detail/My Activities responses
use `Cache-Control: private, no-store` and `Vary: Authorization`; mutation responses
also use `private, no-store`. JWT refresh is stateless: no token revocation/logout
endpoint or refresh-token rotation is currently implemented.

Check-in validates client-reported accuracy and submitted coordinates, not the
authenticity of a device GPS reading. No anti-spoofing, device attestation, or
location history is implemented.
