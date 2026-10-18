# Do Kompletu

## Project overview

Do Kompletu helps people organize and discover real-world group activities, find
participants, and manage their own activities. This repository contains a FastAPI
API and a React web application with a map-based discovery view.

## Current status

The backend supports registration/login, profiles, canonical categories, activity
creation/discovery/details, persisted participation, My Activities, organizer
editing, and soft cancellation. PostgreSQL/PostGIS is the development database.
The organizer editing/cancellation milestone is implemented; attendance workflows
are the recommended next backend milestone.

Frontend authentication, profile display, discovery, details, categories, and
creation use real APIs. My Activities still uses fixtures, and join/leave and
organizer edit/cancel actions still need integration. See
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
    models/        User, Activity, ActivityParticipation
    schemas/       Pydantic request/response and reference-data contracts
    services/      Authentication, profiles, activity and membership rules
    scripts/       Explicit development bootstrap-user command
  alembic/         Versioned database migrations
  docs/            Detailed backend contracts
  tests/           Isolated tests and gated PostgreSQL integration tests
  compose.yaml     Database service
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

Join, leave, edit, and cancel share an activity-row `SELECT ... FOR UPDATE` lock
under explicit PostgreSQL READ COMMITTED isolation. Writers refresh activity
state and check membership/time/capacity after acquiring that lock. This serializes
join vs join, join vs capacity reduction, join vs cancellation, concurrent
organizer updates, and edit vs cancel. The response snapshot is read before commit;
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
and returns a new access token. Sample settings use 30-minute access and 7-day
refresh lifetimes. Protected endpoints accept
`Authorization: Bearer <access_token>`; refresh tokens cannot authorize them.
Swagger uses the separate OAuth2 form endpoint described below.

`GET /api/v1/users/me` returns the authenticated profile; PATCH updates
`display_name` and/or `avatar_url` (null clears the avatar). Points are stored and
returned but no points-awarding/progression system exists.

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
and `offset` (default 0, minimum 0). Cancelled rows are excluded before pagination;
upcoming/ongoing rows come first, then start time ascending and UUID ascending.
Ended activities can still appear.

Detail returns `ActivityRead`, including safe public organizer identity, nullable
`cancelled_at`, caller membership, and action permissions. Authentication is
optional: absent credentials mean anonymous; supplied invalid/expired credentials
return 401. Only the caller's membership is exposed. Public discovery has no
personalized membership/permissions fields.

### Participation

POST `/{activity_id}/join` creates membership (201); DELETE the same path leaves
(200). Both paths are under `/api/v1/activities`, require an access token, take no
body, and return updated `ActivityRead`.

- The organizer is separate from participants, cannot join/leave their own
  activity, and never consumes a participant place.
- Membership persists in `activity_participations`, uniquely keyed by activity
  and user. `participant_count` is derived from these rows; finite
  `available_slots` reflects remaining capacity, while unlimited capacity is null.
- Non-organizers can join/leave before or during an uncancelled activity, strictly
  before `end_at`. Full activities reject new joins. Duplicate joins return 409,
  including when full; leaving without membership, including repeated DELETE, is 409.
- Leaving deletes membership; rejoining creates a new `joined_at`. Ended and
  cancelled memberships remain persisted. Cancellation blocks both join and leave
  with 409, preserving that history. Organizer join/leave is always a 409 conflict.

`current_user_participation` is null or `{status: "JOINED", joined_at: ...}`.
JOINED records membership, not attendance confirmation or check-in. No waitlist
exists. See the [full participation contract](backend/docs/activity-participation.md).

### My Activities

`GET /api/v1/users/me/activities` requires an access token and scopes results to
that user; no client user ID is accepted.

| Parameter | Behavior |
| --- | --- |
| `relation` | Required: `organized` (caller owns activity) or `joined` (caller has membership; owned activities excluded) |
| `scope` | Optional: `upcoming` or `history`; omit for all times, including all organized activities |
| `limit`, `offset` | Default 20/0; limit 1–100, offset ≥ 0 |

One UTC cutoff drives filtering and serialization for the entire page. Upcoming
means `end_at > cutoff`, including ongoing activities, sorted by start then UUID
ascending. History means `end_at <= cutoff`, sorted by end descending then UUID
ascending. Omitted scope puts upcoming first, then history, using those same sorts.
Cancelled activities remain in either relation and use the same end-time scopes;
their status remains CANCELLED.

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

Capacity cannot be reduced below persisted membership (409). Removing the limit
requires `{"has_participant_limit":false,"max_participants":null}`; switching
to FREE requires `{"price_type":"FREE","price_amount":null}`. Enabling a
limit or switching to PAID requires a consistent maximum or price. Omitted values
are not silently cleared.

POST `/api/v1/activities/{activity_id}/cancel` takes no body and allows the
organizer to cancel strictly before `end_at`, including ONGOING activities. It sets
`cancelled_at` once and returns 200 with `ActivityRead`. The activity and all
memberships/counts are preserved. Repeated cancellation and cancellation at/after
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
end. Other users can join/leave subject to membership/capacity before end.
`can_delete` and unsupported future-action permissions remain false.

## API overview

All currently implemented application operations are listed below. “Access JWT”
also requires an active existing user. Interactive docs are at `/docs` and the
generated contract is at `/openapi.json`.

| Method | Endpoint | Authentication | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | Public | API process liveness; does not check database readiness |
| POST | `/api/v1/auth/register` | Public | Register an account |
| POST | `/api/v1/auth/login` | Identifier/password in JSON | Obtain access and refresh tokens |
| POST | `/api/v1/auth/token` | Username/password form | Swagger OAuth2 access token |
| POST | `/api/v1/auth/refresh` | Refresh JWT in JSON | Obtain a new access token |
| GET | `/api/v1/users/me` | Access JWT | Read own profile |
| PATCH | `/api/v1/users/me` | Access JWT | Update own display name/avatar |
| GET | `/api/v1/users/me/activities` | Access JWT | Organized/joined activities by scope |
| GET | `/api/v1/categories` | Public | Canonical category reference data |
| POST | `/api/v1/activities` | Access JWT | Create as authenticated organizer |
| GET | `/api/v1/activities` | Public | Filtered, paginated discovery |
| GET | `/api/v1/activities/{activity_id}` | Optional access JWT | Public detail plus caller state |
| PATCH | `/api/v1/activities/{activity_id}` | Organizer access JWT | Edit before existing start |
| POST | `/api/v1/activities/{activity_id}/cancel` | Organizer access JWT | Soft-cancel before end |
| POST | `/api/v1/activities/{activity_id}/join` | Access JWT; non-organizer | Join membership |
| DELETE | `/api/v1/activities/{activity_id}/join` | Access JWT; non-organizer | Leave membership |

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
```

Replace the JWT placeholder with a long random secret. Settings always load
`backend/.env`, independent of the launch directory. The CORS setting accepts
comma-separated origins or a JSON array.

### Docker/PostgreSQL and migrations

Run from `backend/`:

```powershell
docker compose up -d
docker compose ps
uv run alembic upgrade head
uv run alembic current
```

Compose starts only the `database` service, using `postgis/postgis:17-3.5`.
**Host port 5433 maps to container port 5432.** The development database is
`do_kompletu`; the example user/password are `postgres`/`postgres`. Data lives in
the named `do_kompletu_postgres_data` volume. Wait for its `pg_isready` healthcheck
to report healthy before migrating. Run the API separately; Compose does not
start it or apply migrations.

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
   rejoin. Check real counts and caller-specific permissions at each step.
7. Reauthorize as organizer and cancel. Verify discovery omits the activity,
   direct detail shows CANCELLED, and both users' relevant My Activities lists
   retain it. Repeated cancel, or participant join/leave after cancel, returns 409.

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
uv run pytest -v tests/test_activities_postgres.py tests/test_participation_postgres.py tests/test_my_activities_postgres.py tests/test_activity_management_postgres.py
Remove-Item Env:POSTGRES_TEST_DATABASE_URL
```

Tests use rollback fixtures or commit only generated test records with targeted
cleanup for multi-connection races. They test PostGIS persistence/updates, schema
constraints, timestamps, ordering, counts/privacy, query counts, and actual row
lock contention. Use a local development/test database. Coverage includes auth,
bootstrap, categories, creation/discovery/detail, participation, My Activities,
management/cancellation, and OpenAPI contracts.

Verified on 2026-10-18 after the documentation update:

| Check | Current result |
| --- | --- |
| Default `uv run pytest -v` without integration URL | 246 passed, 32 PostgreSQL tests skipped |
| Separate four-module PostgreSQL run | 32 passed |
| Ruff, compileall, `uv lock --check` | Passed |
| Migration files and development database | `20261018_0005` is head |
| `git diff --check` | Passed |
| `git diff -- frontend` | Empty |

The tests report an existing Starlette TestClient/httpx deprecation warning and
local pytest-cache permission warnings. Git may also report an unreadable root
`.pytest_cache/` directory and LF/CRLF notices; these do not change the test results.

## Database migrations

The verified linear chain and current head are:

| Revision | Exact filename under `backend/alembic/versions/` | Change |
| --- | --- | --- |
| `20260830_0001` | `20260830_0001_create_users_table.py` | Users and unique email |
| `20260927_0002` | `20260927_0002_add_case_insensitive_display_name_unique_index.py` | Case-insensitive display-name uniqueness |
| `20260927_0003` | `20260927_0003_create_activities_table.py` | Activities, PostGIS geography column/index, validation constraints |
| `20261018_0004` | `20261018_0004_create_activity_participations.py` | Unique user/activity memberships, FKs, joined_at, user index |
| `20261018_0005` | `20261018_0005_add_activity_cancellation.py` | Nullable activity cancelled_at; **current head** |

Check file history with `uv run alembic history` and file heads with
`uv run alembic heads`. `uv run alembic current` checks the configured database.
Migration `0005` is additive and preserves activities/memberships. Its downgrade
discards cancellation metadata; `0004` downgrade removes memberships. Historical
upgrade/downgrade probes are recorded in the contracts; normal onboarding uses
`upgrade head`.

## Backend documentation

- [Activity participation contract](backend/docs/activity-participation.md):
  membership storage, join/leave rules, full responses, privacy, and concurrency.
- [My Activities contract](backend/docs/my-activities.md): relation/scope semantics,
  sorting/pagination, full responses, query strategy, and frontend integration.
- [Activity management/cancellation contract](backend/docs/activity-management.md):
  partial editing, cancellation visibility/permissions, locks, errors, and migration validation.

These are the detailed contracts. Their earlier milestone verification tables
are explicitly historical; the current combined verification is listed above.

## Frontend integration status

Verified against the current frontend source; frontend files were not changed by
this documentation update.

| Area | Works now | Remaining integration |
| --- | --- | --- |
| Authentication | Registration, JSON login with correct `identifier` key, access/refresh storage in sessionStorage, session restoration, route protection | Refresh/retry on API 401 beyond session restoration |
| Profile | Real `/users/me` profile displayed through auth context | Profile editing UI for the existing PATCH endpoint |
| Discovery/map/cards | Real activity/category APIs, coordinates, membership counts | Server filtering and pagination beyond the first `limit=100, offset=0` page; lifecycle-aware availability |
| Details | Real optional-auth detail, organizer display, button disabled via `can_join` | Join button has no click handler; no leave or organizer actions |
| Creation | Real form, category/location/time/price/capacity validation, POST, activity-query invalidation, navigation to new detail | Extend mutation/cache coverage for the actions below |
| My Activities | Protected page and three sections exist | Replace mock activities/static membership IDs with authenticated relation/scope queries, loading/errors, and pagination |
| Organizer management | Backend edit/cancel API ready | Edit form/actions, API functions/hooks, cancellation confirmation/error handling, status/cancelled_at rendering |
| Types and caching | Activity status union includes CANCELLED | Membership object/null union, `can_cancel`, `cancelled_at`; user-scoped detail/personal query keys and invalidation/removal on auth changes and mutations |

Current detail queries use activity ID without user identity and stay fresh for
60 seconds; auth changes do not clear query caches. Account changes therefore
need explicit cache handling before exposing personalized membership/actions.
After join/leave/edit/cancel, refresh discovery, detail, and relevant personal lists.
My Activities currently splits fixtures using browser time; integration should use
the API's exact `end_at > cutoff` / `<= cutoff` boundaries and retain cancelled rows.

## Current limitations / not implemented yet

- Waitlists, attendance confirmation, geographic check-in, and verified/completed attendance.
- Reviews, ratings, XP/points progression, ranks, and achievements.
- Notifications, chat, photo galleries/uploads, and media workflows.
- Cancellation reasons, uncancel, activity edit history/audit trail, hard deletion,
  and DRAFT publishing workflows. Concurrent writes to the same field use the
  last successful writer; there is no version/conflict token.
- Payment/refund processing; PAID is descriptive pricing metadata only.
- Nearby radius/distance search and distance calculation; storing coordinates does
  not implement these features. Administrator role-based authorization is absent.

Placeholder fields do not imply implemented features: `tags` is empty,
`distance_m` and confirmation/check-in windows/radius are null,
`checked_in_count`/`waitlist_count` are zero, and future-action permissions are false.
My Activities has no total-count wrapper or cross-page snapshot guarantee.

## Roadmap

| State | Milestone |
| --- | --- |
| Completed backend | Authentication; PostgreSQL/PostGIS setup; profiles; case-insensitive username uniqueness; activity creation/discovery/details; canonical categories; participation; My Activities; organizer editing; soft cancellation |
| Next frontend integration | Real My Activities; join/leave; organizer edit/cancel; cancellation rendering; identity-aware caching and mutation invalidation |
| Recommended next backend milestone | Participation lifecycle / attendance confirmation with explicit states and time-window rules |
| Potential later sequence | Geographic check-in → completed/verified attendance → reviews/ratings → XP/points → ranks/achievements |
| Later product work | Waitlists, notifications/chat, galleries, nearby search; payment handling if required |

Future sequencing is a proposal, not an implemented contract or fixed architecture.

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
