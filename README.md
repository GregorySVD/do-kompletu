# Do Kompletu

## Project overview

Do Kompletu is an API-first application for creating and discovering real-world
group activities. The repository currently contains a FastAPI backend and a frontend
workspace. This document describes the backend contract and local development flow.
Users can create and discover location-based activities, join them, and leave them.
Points, ranks, attendance workflows, and reviews remain future milestones.

## Technology stack

- Python 3.12, FastAPI, Pydantic, and SQLAlchemy 2
- PostgreSQL 17 with PostGIS 3.5
- Alembic database migrations
- JWT access and refresh tokens; Argon2id password hashing
- `uv` for Python dependencies and commands
- Pytest and Ruff for verification
- React, TypeScript, Vite, MUI, and Leaflet in the frontend workspace

## Current status

Implemented:

- account registration with unique email and case-insensitive unique display name;
- JSON login by email or display name, access-token refresh, and an OAuth2 form login
  for Swagger;
- authenticated profile read/update;
- canonical activity categories;
- authenticated activity creation plus public activity list and detail endpoints;
- PostGIS point storage, activity filtering, pagination, and time-derived status;
- authenticated joining/leaving with persisted membership, real participant counts,
  remaining capacity, and caller-specific detail permissions;
- PostgreSQL row locking for concurrent capacity enforcement;
- authenticated organized/joined activity lists with upcoming/history filters,
  deterministic sorting, limit/offset pagination, and caller-specific state.

In progress / next:

- connect frontend join/leave actions and replace the My Activities mocks;
- attendance confirmation and location-based check-in;
- activity editing, cancellation, and deletion;

Later milestones:

- waitlists, gallery/photo workflows, and nearby-distance calculation;
- points, ranks, reviews, notifications, and richer discovery features.

Fields related to these planned features may already appear in activity responses.
Their current placeholder semantics are documented in Swagger.

## Local development

Prerequisites: Docker, Python 3.12, and
[`uv`](https://docs.astral.sh/uv/getting-started/installation/).

Run backend commands from the `backend` directory:

```powershell
cd backend
Copy-Item .env.example .env
docker compose up -d database
uv sync
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

On macOS or Linux, use `cp .env.example .env` instead of `Copy-Item`.

The API is then available at `http://127.0.0.1:8000`, with interactive Swagger UI
at `http://127.0.0.1:8000/docs` and the OpenAPI document at
`http://127.0.0.1:8000/openapi.json`. The compose database is exposed on local port
`5433`.

Review `.env` before starting the service. In particular, replace the example
`JWT_SECRET` with a long random value. `CORS_ALLOWED_ORIGINS` accepts a comma-separated
list (or a JSON list) of trusted frontend origins.

## Frontend integration note

The current frontend already sends `identifier` for login and uses real APIs for
registration, current profile, categories, discovery, details, and activity creation.
Login accepts either email or display name:

```json
{
  "identifier": "user@example.com",
  "password": "..."
}
```

```json
{
  "identifier": "Username",
  "password": "..."
}
```

Participation still needs frontend integration: the detail join button has no
handler, no leave action exists, and `current_user_participation` is typed as only
`null`. My Activities still reads static activity/user fixtures; replace its three
sections with the new current-user activity API described below. Personal query
caches must be scoped to the current user or invalidated on authentication changes, and refreshed
after join/leave along with list counts. An expired supplied access token now yields
401 on detail reads; refresh/retry or clear credentials before anonymous browsing.

The inspected contract, complete join/leave examples, and remaining integration
work are documented in [the participation contract](backend/docs/activity-participation.md).
The inspected My Activities views and their new API mapping are documented in
[the My Activities contract](backend/docs/my-activities.md).
Frontend source files are unchanged.

## Authentication

Frontend login uses JSON:

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "identifier": "Kacper",
  "password": "StrongPassword123"
}
```

`identifier` replaces the older email-only login field and accepts either an email
address or a display name. Display-name lookup is case-insensitive; passwords remain
case-sensitive. Store and send the returned access token as
`Authorization: Bearer <access_token>`. Use the refresh token only with
`POST /api/v1/auth/refresh`.

Swagger's **Authorize** dialog uses a different endpoint:
`POST /api/v1/auth/token`. It accepts form data, returns an access token only, and
uses the OAuth2 field named `username`; enter either an email or display name there.
Leave `client_id` and `client_secret` blank.

Registration and profile update trim surrounding display-name whitespace. Display
names retain the user's capitalization, but PostgreSQL enforces uniqueness with a
unique index on `lower(display_name)`.

## API endpoints

| Method | Path | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | No | Process health check |
| `POST` | `/api/v1/auth/register` | No | Register an account |
| `POST` | `/api/v1/auth/login` | No | JSON login; returns access and refresh tokens |
| `POST` | `/api/v1/auth/token` | No | OAuth2 form login for Swagger; returns access token |
| `POST` | `/api/v1/auth/refresh` | Refresh token body | Issue a new access token |
| `GET` | `/api/v1/users/me` | Access token | Read the current profile |
| `PATCH` | `/api/v1/users/me` | Access token | Update display name and/or avatar URL |
| `GET` | `/api/v1/users/me/activities` | Access token | List your organized/joined activities with time filtering and pagination |
| `GET` | `/api/v1/categories` | No | List canonical activity categories |
| `POST` | `/api/v1/activities` | Access token | Create an activity for the current user |
| `GET` | `/api/v1/activities` | No | List/filter activity projections |
| `GET` | `/api/v1/activities/{activity_id}` | Optional access token | Read details and caller-specific membership/permissions |
| `POST` | `/api/v1/activities/{activity_id}/join` | Access token | Join; return updated details (201) |
| `DELETE` | `/api/v1/activities/{activity_id}/join` | Access token | Leave; return updated details (200) |

For the complete request rules, selectable examples, category UUIDs, responses, and
error shapes, use Swagger UI. The create-activity operation documents participant,
time, location, category, and `FREE`/`PAID` consistency rules.

## Activity participation

Join and leave accept no request body. Use a different account from the organizer
and send `Authorization: Bearer <access_token>`. Both return `ActivityRead`, including
updated counts and `current_user_participation` (`{"status":"JOINED","joined_at":"..."}`
after joining, `null` after leaving).

- Organizers are separate from membership: they cannot join/leave their own event
  and do not consume a participant place. Creation still starts with zero participants.
- Non-organizers can join before/during an activity, strictly before `end_at`.
- A finite `max_participants` limits persisted membership; `null` is unlimited.
- Leaving removes membership and frees a place. Rejoining is allowed while eligible.
- Ended membership is preserved for history; joining/leaving after the end is rejected.
- Missing credentials return 401; unknown activities return 404. Duplicate joining,
  full capacity, organizer actions, ended activities, and leaving without membership
  return 409 with the normal `{"detail":"..."}` error body. Repeated DELETE returns
  409; state remains unchanged.
- `participant_count` counts persisted membership rows, excluding the organizer.
  `available_slots` is `max_participants - participant_count`, or `null` if unlimited.
  Checked-in/waitlist counts remain zero; membership does not confirm attendance.
- Anonymous detail reads return null membership and false permissions. Authenticated
  details expose only the caller's membership. Supplied invalid credentials return
  401; omit Authorization for anonymous browsing. Detail responses use
  `Cache-Control: private, no-store` and `Vary: Authorization`.
- `can_join` and `can_leave` reflect these rules. All unimplemented permissions,
  including organizer edit/delete, remain false.

Every join/leave transaction locks the parent activity using `SELECT ... FOR UPDATE`
before reading membership/capacity, and holds that lock through insertion/deletion,
the updated response snapshot, and commit. The application explicitly uses PostgreSQL
READ COMMITTED isolation, so a waiting writer counts the preceding writer's committed
rows. A composite primary key also prevents duplicate membership. All future membership/capacity
writers must follow the same locking protocol; direct SQL writes bypass business rules.
Counts are queried from rows instead of maintained as mutable counters.

## My Activities

Use an access JWT with `GET /api/v1/users/me/activities`. Identity always comes
from the token. The response is an array of existing `ActivityRead` objects,
including real counts, the caller's membership, and permissions; no wrapper or
new response DTO is introduced.

| Query field | Values/default | Meaning |
| --- | --- | --- |
| `relation` | Required: `organized` or `joined` | Your organizer identity or your persisted membership; organizers are separate from participants |
| `scope` | Optional: `upcoming` or `history` | Omit to include all times, as required by the current organized section |
| `limit` | Default 20; 1-100 | Maximum matching records returned |
| `offset` | Default 0; nonnegative | Matching records to skip after filtering/sorting |

Map the current frontend's sections to these requests:

```http
GET /api/v1/users/me/activities?relation=joined&scope=upcoming&limit=20&offset=0
GET /api/v1/users/me/activities?relation=organized&limit=20&offset=0
GET /api/v1/users/me/activities?relation=joined&scope=history&limit=20&offset=0
Authorization: Bearer <access_token>
```

`upcoming` means `end_at > cutoff` and includes ongoing activities. `history` means
`end_at <= cutoff`; the exact end instant is history. A single UTC cutoff drives
filtering, status, and permissions for the whole page. Upcoming sorts by start time
ascending; history sorts by end time descending. When scope is omitted, upcoming
comes first with that ordering, followed by history with its ordering. UUID
ascending breaks ties in every case.

Joined items contain the caller's `JOINED` membership; organized items normally
have null membership and management permissions remain false. Checked-in/waitlist
counts remain zero; unlimited activities keep `available_slots: null`.

An empty result or out-of-range offset returns `[]`. There is no total count or
`has_more`. Fetch successive offsets until a short/empty page; a full last page
may require an additional empty fetch. Time/membership changes between requests can
shift offsets; this is not a frozen snapshot across pages. Authentication failures
return 401. Missing/invalid filters, pagination, and unknown query fields (including
`user_id`) return 422. Personal responses use `Cache-Control: private, no-store`
and `Vary: Authorization`.

One activity SELECT includes the organizer, correlated participant count, and
caller membership; authentication adds one user lookup. Query-count tests against
SQLite and PostgreSQL verify that larger pages do not add SQL round trips per item.
The public list retains its response shape and one-SELECT query path. No database
schema changes or new migrations are needed; the head remains `20261018_0004`.

Frontend work remains: add an authenticated API function/query hook, replace the
mock sections, add page loading/error/load-more states, update the membership type,
and scope caches to user identity plus relation/scope/pagination. The server owns
the time classification; remove the current browser-clock split at integration.
No edit/cancel/delete controls currently exist in this page; their APIs remain
outside this milestone.

## Optional bootstrap user

A repeatable development account can be created without embedding credentials in
source code. Set all three variables in your local `.env`:

```dotenv
BOOTSTRAP_USER_EMAIL=developer@example.com
BOOTSTRAP_USER_DISPLAY_NAME=Developer
BOOTSTRAP_USER_PASSWORD=choose-a-local-password
```

Then run:

```powershell
uv run python -m app.scripts.create_bootstrap_user
```

The command is for development/testing only and is disabled when
`ENVIRONMENT=production`. The password is passed through the normal Argon2id hashing
flow. The command is idempotent: an exact existing account is left unchanged,
including its password. It fails safely if the configured email and display name
resolve to conflicting accounts. This creates an ordinary development user, not an
administrator role. Keep real credentials out of `.env.example` and version control.

## Database migrations

The migration history is append-only:

- `20260830_0001` creates users;
- `20260927_0002` adds the PostgreSQL unique functional index on
  `lower(display_name)`;
- `20260927_0003` creates activities, PostGIS geography storage, constraints, and
  indexes;
- `20261018_0004` adds `activity_participations`: UUID activity/user foreign keys with
  cascading cleanup, composite primary key, `joined_at` timestamptz defaulting to
  `now()`, and an index on user ID. A row represents active membership. No speculative
  status/history/reward columns are added; later migrations can extend the relation.

Apply and inspect migrations with:

```powershell
uv run alembic upgrade head
uv run alembic current
```

To validate the latest migration's downgrade/upgrade cycle against a disposable or
development database:

```powershell
uv run alembic downgrade -1
uv run alembic upgrade head
```

Do not run a downgrade against production without a reviewed rollback plan and a
backup. Downgrading `0004` drops membership data while preserving users and activities.
Prefer validating rollback in a temporary database. A new database must have the
PostGIS extension enabled before applying the existing activity migration.

## Testing and quality checks

From `backend`:

```powershell
uv run pytest -v
uv run ruff check .
uv run python -m compileall app
uv lock --check
```

Most tests use an isolated SQLite setup with foreign keys enabled. PostgreSQL/PostGIS
tests are skipped unless `POSTGRES_TEST_DATABASE_URL` is set
to a migrated PostgreSQL database:

```powershell
$env:POSTGRES_TEST_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE"
uv run pytest -v tests/test_activities_postgres.py tests/test_participation_postgres.py tests/test_my_activities_postgres.py
```

Do not point integration tests at production data. Membership integration fixtures
commit only generated test UUIDs, exercise independent connections, and delete only
their own records afterward. They test schema constraints/defaults, cascades, API
projections, and concurrent final-place joins, duplicate joins, and join/leave races.
The concurrency test holds the activity lock until both workers visibly wait in
`pg_stat_activity`, then checks serial outcomes and capacity. SQLite tests do not
claim to validate PostgreSQL locking. The final-place scenario uses capacity two
with one existing member because the established creation contract requires at least two.
My Activities integration fixtures roll back an outer PostgreSQL transaction and
test real timestamptz values under multiple connection time zones, UUID tie ordering,
PostGIS projections, scoped state, pagination, and constant query counts.

## Known limitations

- Waitlist, confirmation, check-in, gallery, upload, and organizer edit/delete
  permissions remain `false`; corresponding workflows are not implemented.
- Checked-in and waitlist counts remain `0`. Membership is not attendance confirmation.
- `distance_m` is currently `null`; nearby search is not implemented.
- Categories are fixed application reference data rather than database-managed rows.
- Activity status is derived from the current time and the stored start/end times.
- My Activities backend lists are implemented, but the frontend still uses mocks.
- My Activities uses limit/offset arrays without total counts or a frozen cross-page snapshot.
- Leaving removes the membership row; leave/rejoin audit history is not stored.
- Capacity is enforced by the service locking protocol, not by a database count trigger.
- Role-based administrator authorization is not implemented.

## Security notes

- Never commit `.env`, production credentials, JWT secrets, or bootstrap passwords.
- Use a strong, environment-specific `JWT_SECRET` and HTTPS in production.
- Passwords are stored as salted Argon2id hashes and are never returned by the API.
- Access and refresh tokens have distinct types and lifetimes; do not use refresh
  tokens as bearer authorization.
- Activity organizer identity is derived from the authenticated access JWT and cannot
  be selected by the client.
- Restrict CORS origins to trusted deployed frontends.
- Run migrations with a database role limited to the required schema operations, and
  run the application with a less-privileged role where deployment policy permits.
