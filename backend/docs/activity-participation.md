# Activity participation contract

## Repository/frontend findings (2026-10-18)

The work uses the existing `backend` branch and leaves `frontend/` unchanged.
Both the migration-file head and the development database started at `20260927_0003`.
Compose and the local settings use PostgreSQL on host port **5433**.

| Area inspected | Current frontend behavior | Backend assessment |
| --- | --- | --- |
| `api/authApi.ts`, auth types/context, login form | JSON `identifier` login, registration, access/refresh tokens, `/users/me` | Compatible; the old README email-login warning was obsolete. Refresh currently happens during session restoration, not after every API 401. |
| `api/apiClient.ts` | Axios sends the sessionStorage access token on all requests | Compatible with optional detail auth; supplied expired/invalid credentials now cause 401 rather than being ignored. |
| List, map, cards, queries, local filters | Real activity/category APIs, numeric coordinates/counts, nullable capacity, enum prices | Existing names/types match. Counts/capacity now come from membership. The UI's missing-to-minimum calculation is presentation logic and can stay local. |
| Discovery pagination | Fetches only `limit=100, offset=0`, then filters locally | It is not a complete dataset beyond 100 results. Server filtering already exists; pagination/filter integration is later frontend work. Availability filtering currently checks slots but not lifecycle. |
| Detail page and detail query | Real API; reads `permissions.can_join`; button has no click handler; no leave UI | No existing join/leave network contract to preserve. Detail query key contains activity ID but no user identity. |
| Activity/user TypeScript types | Detail membership declared as exactly `null`; user shape matches `/users/me` | Update membership to the object/null union below when wiring participation. Status union also permits DRAFT/CANCELLED, which the backend does not currently produce. |
| Creation form, Zod schema, mutation | Canonical categories, snake_case payload, timezone-aware dates, consistent price/capacity values | Compatible. Frontend additionally forbids past starts; backend preserves its existing allowance for past/ongoing activities. Backend enforces category IDs and decimal amount bounds more strictly. |
| Profile/current user | Real auth-context user and `/users/me` | Compatible. Profile update API remains available; this page currently displays profile data. |
| Routing/permissions | Public discovery/detail; protected creation/profile/My Activities | Compatible. Backend independently enforces write authentication and business rules. |
| My Activities and fixture files | `mockActivities` plus static `mockUserActivities` IDs, split locally into upcoming/organized/history | No real API call or query contract exists here. No speculative My Activities endpoint was added. Static IDs may lead to real detail 404s; mock permissions/counts are not authoritative. |

## Storage and transactions

Migration: `20261018_0004_create_activity_participations.py`, revision
`20261018_0004`, parent `20260927_0003`.

```sql
CREATE TABLE activity_participations (
    activity_id uuid NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_activity_participations PRIMARY KEY (activity_id, user_id)
);
CREATE INDEX ix_activity_participations_user_id
    ON activity_participations (user_id);
```

A row means active membership. There is no speculative persisted status, surrogate
ID, confirmation, attendance, or reward state. Leaving deletes the row; a later join
creates a new timestamp. Future migrations can extend the relationship with lifecycle
fields without changing the user/activity identity. Leave/rejoin audit history is
not recorded in this milestone. Cascades apply when referenced rows are deleted;
this does not introduce user/activity deletion APIs.

The service locks the activity row with `SELECT ... FOR UPDATE`, then checks role,
membership, current time, and capacity, inserts/deletes membership, reads the updated
detail snapshot, and commits. Both operations roll back on failures. The response
snapshot is read while holding the lock; later transactions can naturally change
the activity after commit.

The application explicitly configures PostgreSQL READ COMMITTED isolation, which
gives each subsequent query a fresh snapshot. A writer
waiting for the activity lock therefore sees the previous writer's committed
membership before counting places. All membership and future capacity writers must
follow this protocol. Direct SQL inserts are protected against duplicate membership
and missing foreign keys, but do not enforce capacity, lifecycle, or organizer rules.
Higher transaction isolation would require separate retry/isolation design.

List/detail counts use correlated SQL projections against the composite primary-key
index. They neither load participant lists nor issue one membership query per item.
Caller membership is queried only for the authenticated caller; public list items
keep their existing shape.

## Endpoints and complete examples

Join and leave take **no request body**. Obtain a real UUID by creating/listing an
activity and use a different user from its organizer. Example UUIDs and timestamps
below are illustrative. Swagger provides the same complete response examples,
authentication instructions, and selectable error examples.

```http
POST /api/v1/activities/d54112d9-43cf-4986-8679-b6c236ac522c/join
Authorization: Bearer <access_token>
```

201 Created, `Content-Type: application/json`:

```json
{
  "id": "d54112d9-43cf-4986-8679-b6c236ac522c",
  "title": "Siatkówka na Orliku",
  "category": {
    "id": "623c6216-f59e-4167-a238-bfda04d99488",
    "name": "Sport zespołowy",
    "slug": "sport-zespolowy"
  },
  "start_at": "2030-08-08T16:00:00Z",
  "end_at": "2030-08-08T18:00:00Z",
  "location_name": "Orlik przy ul. Gdańskiej",
  "address": "ul. Gdańska 1, Poznań",
  "latitude": 52.4232,
  "longitude": 16.9461,
  "distance_m": null,
  "price_type": "FREE",
  "min_participants": 4,
  "max_participants": 12,
  "participant_count": 1,
  "checked_in_count": 0,
  "waitlist_count": 0,
  "available_slots": 11,
  "status": "PUBLISHED",
  "description": "Amatorski mecz siatkówki dla każdego chętnego.",
  "organizer": {
    "id": "bb1aedb3-54f4-45c4-ab10-2fb0a07b53ca",
    "display_name": "Organizer",
    "avatar_url": null
  },
  "tags": [],
  "confirmation_opens_at": null,
  "confirmation_deadline_at": null,
  "checkin_opens_at": null,
  "checkin_closes_at": null,
  "checkin_radius_m": null,
  "price_amount": null,
  "currency": null,
  "current_user_participation": {
    "status": "JOINED",
    "joined_at": "2030-08-01T12:00:00Z"
  },
  "permissions": {
    "can_edit": false,
    "can_delete": false,
    "can_join": false,
    "can_leave": true,
    "can_confirm": false,
    "can_check_in": false,
    "can_view_gallery": false,
    "can_upload_photo": false
  }
}
```

```http
DELETE /api/v1/activities/d54112d9-43cf-4986-8679-b6c236ac522c/join
Authorization: Bearer <access_token>
```

200 OK, `Content-Type: application/json`:

```json
{
  "id": "d54112d9-43cf-4986-8679-b6c236ac522c",
  "title": "Siatkówka na Orliku",
  "category": {
    "id": "623c6216-f59e-4167-a238-bfda04d99488",
    "name": "Sport zespołowy",
    "slug": "sport-zespolowy"
  },
  "start_at": "2030-08-08T16:00:00Z",
  "end_at": "2030-08-08T18:00:00Z",
  "location_name": "Orlik przy ul. Gdańskiej",
  "address": "ul. Gdańska 1, Poznań",
  "latitude": 52.4232,
  "longitude": 16.9461,
  "distance_m": null,
  "price_type": "FREE",
  "min_participants": 4,
  "max_participants": 12,
  "participant_count": 0,
  "checked_in_count": 0,
  "waitlist_count": 0,
  "available_slots": 12,
  "status": "PUBLISHED",
  "description": "Amatorski mecz siatkówki dla każdego chętnego.",
  "organizer": {
    "id": "bb1aedb3-54f4-45c4-ab10-2fb0a07b53ca",
    "display_name": "Organizer",
    "avatar_url": null
  },
  "tags": [],
  "confirmation_opens_at": null,
  "confirmation_deadline_at": null,
  "checkin_opens_at": null,
  "checkin_closes_at": null,
  "checkin_radius_m": null,
  "price_amount": null,
  "currency": null,
  "current_user_participation": null,
  "permissions": {
    "can_edit": false,
    "can_delete": false,
    "can_join": true,
    "can_leave": false,
    "can_confirm": false,
    "can_check_in": false,
    "can_view_gallery": false,
    "can_upload_photo": false
  }
}
```

`GET /api/v1/activities/{activity_id}` accepts optional authentication. With the
participant's token it returns the same membership shape as join; without a token
it returns null membership and all false permissions. Another user's token only
reveals that caller's state. Detail uses `Cache-Control: private, no-store` and
`Vary: Authorization`; mutation responses also use `private, no-store`.

`GET /api/v1/activities` preserves its public list-item shape and now reports real
counts/capacity. Unlimited activities have `max_participants: null` and
`available_slots: null`. Checked-in/waitlist counts remain zero everywhere.

## Business rules, errors, and permissions

Organizers are separate from participants and never consume capacity. Non-organizers
may join/leave before or during the activity, strictly before its end. Membership
is preserved after the end. All future permissions remain false, including edit and
delete because their endpoints are not implemented.

| Caller/state | can_join | can_leave |
| --- | --- | --- |
| Anonymous | false | false |
| Organizer | false | false |
| Authenticated non-member, open, space available/unlimited | true | false |
| Authenticated non-member, full | false | false |
| Participant, before end (even if full) | false | true |
| Any caller after end | false | false |

| Status | Exact JSON body | Applies to |
| --- | --- | --- |
| 401 | `{"detail":"Not authenticated"}` | Missing credentials on join/leave (OAuth2 dependency) |
| 401 | `{"detail":"Could not validate credentials"}` | Invalid, expired, inactive-user, unknown-user, or refresh bearer token |
| 404 | `{"detail":"Activity not found"}` | Unknown activity |
| 409 | `{"detail":"Organizer cannot join or leave their own activity"}` | Both mutations by organizer |
| 409 | `{"detail":"Already joined this activity"}` | Duplicate POST, even when full |
| 409 | `{"detail":"Not participating in this activity"}` | DELETE without membership, including repeat DELETE |
| 409 | `{"detail":"Activity has ended"}` | New join or participating user's leave at/after end |
| 409 | `{"detail":"Activity is full"}` | New join with no remaining places |
| 422 | Standard FastAPI validation body | Invalid activity UUID |

Checks run in this order: existence, organizer, membership, end time, capacity.
Repeated DELETE preserves state but returns 409; rejoining after leaving is allowed.

## Validation and remaining work

The isolated suite covers successful/duplicate joins, authentication failures,
missing/invalid activities, public/caller privacy, counts, pagination, capacity,
unlimited events, successful/repeated leave, rejoin, organizer rules, ongoing/end
boundary behavior, FK integrity, uniqueness, and cascades. Existing auth, category,
activity, bootstrap-user, and Swagger tests remain in place.

PostgreSQL tests separately cover PostGIS round trips, migrated schema/defaults,
unique/FK constraints, cascading cleanup, HTTP projections, and three concurrency
scenarios. Each race proves both workers wait on real PostgreSQL locks before
releasing the holder; the final-place scenario admits exactly one new member.
SQLite is used only for isolated functional coverage.

The development database was upgraded additively. A temporary PostGIS database
validated baseline `0003`, upgrade `0004`, schema/indexes/FKs, downgrade to `0003`
(membership table absent), and re-upgrade to `0004`; the temporary database was
removed afterward. No persistent volume was removed.

Final verification:

| Check | Result |
| --- | --- |
| `uv run pytest -v` | 117 passed, 11 PostgreSQL tests skipped without the integration URL |
| `uv run pytest -v tests/test_activities_postgres.py tests/test_participation_postgres.py` with the integration URL | 11 passed, including all three real lock-contention scenarios |
| `uv run ruff check .` | Passed |
| `uv run python -m compileall app` | Passed |
| `uv lock --check` | Passed; 66 packages resolved, lockfile unchanged |
| `uv run alembic current` | `20261018_0004 (head)` in the development database |
| Upgrade/downgrade/re-upgrade | Passed against a temporary PostgreSQL 17/PostGIS database |
| Application database configuration | `localhost:5433`, READ COMMITTED verified from an actual connection |
| Complete documentation examples | Parsed and matched to the API response examples exactly |
| Data cleanup | Original development user preserved; zero activities/memberships after tests |
| `git diff --check` and frontend diff | Passed; frontend unchanged |

The test runs report the existing Starlette TestClient/httpx deprecation and a
local pytest-cache directory permission warning. Neither warning was suppressed.
Git also reports a pre-existing unreadable root pytest-cache directory and normal
LF-to-CRLF notices. No commits, pushes, branch merges, or resets were performed.

Frontend follow-up:

1. Change the membership type to `{ status: 'JOINED'; joined_at: string } | null`.
2. Add join/leave API functions and mutation hooks; render pending/error/leave states
   using backend permissions. Refetch/invalidate detail and list counts after mutation.
3. Scope detail query keys to user identity, or remove/invalidate personalized queries
   on login/logout/account changes; account for session restoration before fetching.
4. Handle 401 through access-token refresh/retry or by clearing tokens and refetching
   anonymously. Current refresh-on-session-restoration alone is insufficient.
5. Replace My Activities fixtures once an authenticated organized/joined list contract
   is designed. No such endpoint exists in this milestone.
6. Integrate server pagination/filtering for discovery beyond its first 100 records;
   consider ended status when presenting available activities.

Recommended next backend milestone: authenticated organized/joined activity lists,
including pagination and clear upcoming/history semantics, followed by organizer
editing/cancellation using the same activity lock for capacity/lifecycle changes.
Waitlists, attendance confirmation/check-in, reviews, XP, ranks, achievements, media,
notifications, and distance search remain unimplemented.
