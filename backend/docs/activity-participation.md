# Activity participation lifecycle contract

## Scope and compatibility

The current lifecycle replaces row-existence membership with retained JOINED/CONFIRMED/CHECKED_IN/LEFT
state. Existing join (201), leave (200), ActivityRead responses, organizer separation,
JWT authentication, and cancellation rules remain. Leave keeps its DELETE URL but
now changes state instead of deleting the record. New confirmation uses
`POST /api/v1/activities/{activity_id}/confirm` (200), without a request body.
PostGIS check-in adds `POST /api/v1/activities/{activity_id}/check-in` with coordinate
JSON. Its detailed window, proximity, privacy, and error contract is in
[Activity check-in](activity-check-in.md). Current migration head is 0007.

The [README](../../README.md#testing) records current verification. Related contracts
cover [My Activities](my-activities.md) and [organizer management](activity-management.md).

## Repository/frontend inspection

Frontend files were inspected and left unchanged. `frontend/src/types/activity.ts`
already declares nullable `confirmation_opens_at`, `confirmation_deadline_at`, and
`permissions.can_confirm`. These existing fields are activated, without introducing
another timing object. The backend previously exposed only a JOINED membership
status with joined_at; it now supports CONFIRMED/CHECKED_IN and nullable
confirmed_at/checked_in_at. Existing checkin_* metadata and can_check_in are reused;
details already render a passive timing/radius panel. There is no geolocation utility.

| Frontend area | Current behavior | Required integration |
| --- | --- | --- |
| Activity types | current_user_participation is typed as exactly null | Add JOINED/CONFIRMED/CHECKED_IN object/null union and joined_at/confirmed_at/checked_in_at; add can_cancel/cancelled_at |
| Detail | Real API; join button reads can_join but has no handler | Join/leave/rejoin/confirm API functions and hooks; pending/error states, confirmed indication, window UI |
| My Activities | Static mockActivities and mockUserActivities IDs, browser-clock sections | Real relation/scope queries, loading/errors/pagination; LEFT excluded, server time boundaries authoritative |
| Timing/mocks | Passive check-in panel and types exist; fixtures also contain future-feature fields | Use live timing/radius/can_check_in; add geolocation and check-in mutation/actions/errors; fixture dates are not business rules |
| Caching | Detail key includes activity ID, not identity; 60-second freshness | User-scoped detail/personal keys or removal on auth changes; invalidate list/detail/personal data after create/join/leave/confirm/check-in/edit/cancel |
| Auth/client | Correct identifier JSON login, sessionStorage bearer tokens on requests | Access-token refresh/retry on 401 beyond session restoration |
| Management/status | No organizer controls or cancellation badges | Edit/cancel integration; display CANCELLED and blocked actions |

The API never exposes someone else's participation or confirmed_at. LEFT is an
internal inactive record, not a new status to render as current participation.

## Persistence and migration

`20261018_0006_add_participation_lifecycle.py` follows verified parent
`20261018_0005`. It adds:

| Column | Persistence |
| --- | --- |
| status | VARCHAR(16), NOT NULL, server/Python default JOINED |
| joined_at | Existing NOT NULL timestamptz; latest active-cycle join time |
| left_at | Nullable timestamptz; required for LEFT |
| confirmed_at | Nullable timestamptz; required for CONFIRMED; preserved after leaving |
| checked_in_at | Added by 0007; nullable timestamptz required only for CHECKED_IN; no participant location columns |

The existing `(activity_id, user_id)` primary key, CASCADE foreign keys, and user
index remain. Existing rows become JOINED with original joined_at and null new
timestamps. A VARCHAR plus CHECK avoids PostgreSQL native-enum migration coupling;
future states can be added through an explicit migration and shared active-state
definition. JOINED, CONFIRMED, CHECKED_IN, and LEFT are accepted now.

Database CHECKs enforce valid status and state/timestamp consistency:

- JOINED: left_at, confirmed_at, and checked_in_at are null.
- CONFIRMED: left_at/checked_in_at are null and confirmed_at is present.
- CHECKED_IN: confirmed_at/checked_in_at are present and left_at is null.
- LEFT: left_at is present, checked_in_at is null; confirmed_at may retain last-cycle confirmation.

Upgrade is additive. Downgrade to 0005 **deletes LEFT records** so that the old
row-existence model does not reactivate them, retains JOINED/CONFIRMED rows, and
removes lifecycle/confirmation metadata. Re-upgrade makes surviving rows JOINED.
Downgrading therefore loses history and confirmation; it is tested only in a
generated temporary PostGIS database, never against development data.
The next migration, 0007, preserves all existing states; its downgrade converts
CHECKED_IN to CONFIRMED and drops only check-in metadata while retaining every row.

## States, capacity, and timestamps

| State | Active / consumes a place | Current participation | Joined My Activities |
| --- | --- | --- | --- |
| JOINED | Yes | JOINED + joined_at + null confirmed_at | Included |
| CONFIRMED | Yes | CONFIRMED + joined_at + confirmed_at | Included |
| CHECKED_IN | Yes | CHECKED_IN + joined_at + confirmed_at + checked_in_at | Included |
| LEFT | No | null | Excluded, including history scope |

`ACTIVE_PARTICIPATION_STATUSES` in the participation model centralizes active
states. Capacity/counts, membership projections, and joined-list predicates use it
in SQL. `participant_count` is JOINED + CONFIRMED + CHECKED_IN, excluding the organizer.
checked_in_count counts CHECKED_IN only, not CONFIRMED; waitlist_count remains zero.
Finite available_slots is maximum minus that count; unlimited remains null.
LEFT frees a seat even though its record remains stored. Cancellation does not
change participation statuses; its preserved active rows still count.

| Transition | Endpoint | Stored changes |
| --- | --- | --- |
| No row → JOINED | POST /api/v1/activities/{activity_id}/join | Insert joined_at; null left_at/confirmed_at |
| LEFT → JOINED | Same POST | Reuse the row, replace joined_at, clear left_at/confirmed_at/checked_in_at |
| JOINED → CONFIRMED | POST /api/v1/activities/{activity_id}/confirm | Set confirmed_at; preserve joined_at |
| JOINED/CONFIRMED → LEFT | DELETE /api/v1/activities/{activity_id}/join | Set left_at; preserve joined_at and confirmed_at |
| CONFIRMED → CHECKED_IN | POST /api/v1/activities/{activity_id}/check-in | Set checked_in_at after time/PostGIS validation |

Only check-in requires a coordinate body; join/leave/confirm take no body.
CHECKED_IN cannot leave, rejoin, confirm, or check in again. Leaving/rejoining is not an immutable event
log: one row describes the latest cycle and loses earlier-cycle evidence on rejoin.
There is no unconfirm, undo check-in, automatic expiry/removal, completed attendance,
no-show, waitlist, or rewards in this milestone. JOINED after the deadline remains
an active membership; confirmation is self-declared intent, not verified attendance.

## Confirmation window and permissions

`ACTIVITY_CONFIRMATION_WINDOW_HOURS` is an integer setting, default 24, range
1–8760. It is documented in backend/.env.example. One shared rule derives:

```text
confirmation_opens_at = start_at - configured window
confirmation_deadline_at = start_at
allowed exactly when opens_at <= now < deadline_at
```

All comparisons use timezone-aware UTC. Very early supported dates clamp the
opening to the minimum representable UTC datetime. Nominal timing is public in
ActivityRead (detail, mutation responses, and My Activities), including after end
or cancellation; timing alone never implies an allowed action. Discovery's list
shape is unchanged. Changing the setting changes derived timing immediately after
the application reloads settings; no database timing columns are introduced.

| Permission | True only when |
| --- | --- |
| can_join | Authenticated non-organizer, no active membership (including LEFT), uncancelled, before end, capacity available/unlimited |
| can_leave | Authenticated non-organizer with JOINED/CONFIRMED, uncancelled, before end |
| can_confirm | Authenticated non-organizer with JOINED, uncancelled, inside the confirmation window |
| can_check_in | CONFIRMED non-organizer, uncancelled, within check-in window before end; allows an attempt, not a proximity guarantee |

Confirmed users cannot confirm again but may leave until the existing end boundary.
All cancelled permissions are false. Organizer edit/cancel permissions retain their
lifecycle rules; can_edit does not promise every proposed field change is valid.

## Errors and privacy

| Status | Exact detail / meaning |
| --- | --- |
| 401 | Missing access token: `Not authenticated`; invalid/expired/refresh token or unavailable user: `Could not validate credentials` |
| 404 | `Activity not found` |
| 409 | `Organizer cannot join or leave their own activity` |
| 409 | `Organizer cannot confirm their own activity` |
| 409 | `Activity is cancelled` |
| 409 | `Activity has ended` |
| 409 | `Already joined this activity` for duplicate JOINED/CONFIRMED/CHECKED_IN POST, including when full |
| 409 | `Activity is full` for new join or LEFT rejoin |
| 409 | `Not participating in this activity` for leave/confirm without active membership, including repeated leave |
| 409 | `Already confirmed attendance` |
| 409 | `Already checked in` for confirm/check-in after CHECKED_IN |
| 409 | `Checked-in participants cannot leave` |
| 409 | `Confirmation window has not opened` |
| 409 | `Confirmation window has closed` at/after start while not ended |
| 422 | Standard FastAPI validation body for malformed activity UUID |

Domain errors use `{"detail":"message"}`. After input validation/authentication,
all mutations check activity existence, organizer identity, then cancellation.
Join/leave next check membership, end time, then capacity for join. Confirmation
checks end time, active membership, already-confirmed state, then its window.
All conflict paths roll back; failed rejoin leaves the LEFT row untouched.

Detail authentication remains optional: missing credentials are anonymous;
supplied invalid credentials return 401. Caller state is null for anonymous,
unrelated, and LEFT users. Detail/My Activities use `Cache-Control: private,
no-store` and `Vary: Authorization`; mutations use private, no-store.

## Management and PostgreSQL transactions

Every join/leave/confirm/check-in/edit/cancel writer locks the activity row first under
explicit READ COMMITTED, refreshes cached ORM state, and holds the lock through
validation, writes, and response projection until commit. Participation lookups
also use populate_existing after the parent lock, preventing stale cached statuses
from overwriting another transaction. No inconsistent membership-first lock path
is introduced. Time is evaluated after waiting for the lock.

Actual start_at/end_at changes are rejected with 409 while any row is CONFIRMED/CHECKED_IN.
CHECKED_IN additionally blocks actual latitude/longitude/location_name/address changes.
Unchanged equivalent timestamps and other permitted edits remain valid. LEFT rows
with historical confirmed_at do not block schedule changes. Capacity changes use
the same active-state count; no confirmations are silently cleared.

Cancellation retains JOINED, CONFIRMED, CHECKED_IN, and LEFT records and timestamps, excludes
the activity from discovery, retains direct detail/organized lists and active
joined lists, and blocks join/rejoin/leave/confirm/check-in. Scope still follows end_at.

Counts and caller state remain correlated SQL projections, with eager-loaded
organizer identity. No participant lists are loaded merely to count. Public lists
remain one SELECT and My Activities two including auth, independent of page size.
PATCH remains four SELECTs and cancel three including auth; confirm has three
SELECTs in the service (lock, membership, response), plus HTTP authentication.
Database work still grows with matching rows; constant round trips are not a
constant CPU-time claim. Existing activity/user indexes support these predicates.

## Validation and frontend follow-up

Isolated coverage includes all state transitions, retained timestamps/rejoin,
capacity, private/current projections, My Activities, exact microsecond window
boundaries, configurable timing, permissions, schedule restrictions, cancellation,
failed-write rollback, and OpenAPI. PostgreSQL coverage validates migrated CHECKs,
defaults/backfill, uniqueness, real UTC/time-zone behavior, and SELECT counts.

Eight contention scenarios run in both observed PostgreSQL lock orders: final
slot, full leave vs join, LEFT rejoin vs new join, confirm vs leave, confirm vs
cancel, confirm vs schedule edit, confirmed capacity reduction vs rejoin, and
duplicate confirmation. Each test holds the parent lock and observes both queued
writers before releasing it. Temporary-database migration coverage exercises
0005 → 0006 → 0005 → 0006 and removes only that generated database afterward.

Frontend work remains as listed above: live membership/status/timestamps, API
functions/mutations, window/button/error UI, real My Activities, cancellation
rendering, geolocation/check-in actions, identity-aware caches, and invalidation. Attendance completion/no-show,
reviews, rewards, media, messaging, payments, and a full participation audit log
remain future work. Current combined results are in the README.

## Complete response examples

Examples use illustrative IDs/dates and the default 24-hour window. Swagger includes
the same complete responses and error choices. The caller is a participant, not
the organizer. The following snapshots show joined, left, and confirmed responses.

### Joined response (201)

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
  "cancelled_at": null,
  "description": "Amatorski mecz siatkówki dla każdego chętnego.",
  "organizer": {
    "id": "bb1aedb3-54f4-45c4-ab10-2fb0a07b53ca",
    "display_name": "Organizer",
    "avatar_url": null
  },
  "tags": [],
  "confirmation_opens_at": "2030-08-07T16:00:00Z",
  "confirmation_deadline_at": "2030-08-08T16:00:00Z",
  "checkin_opens_at": "2030-08-08T15:30:00Z",
  "checkin_closes_at": "2030-08-08T17:00:00Z",
  "checkin_radius_m": 150,
  "price_amount": null,
  "currency": null,
  "current_user_participation": {
    "status": "JOINED",
    "joined_at": "2030-08-01T12:00:00Z",
    "confirmed_at": null,
    "checked_in_at": null
  },
  "permissions": {
    "can_edit": false,
    "can_cancel": false,
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

### Left response (200)

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
  "cancelled_at": null,
  "description": "Amatorski mecz siatkówki dla każdego chętnego.",
  "organizer": {
    "id": "bb1aedb3-54f4-45c4-ab10-2fb0a07b53ca",
    "display_name": "Organizer",
    "avatar_url": null
  },
  "tags": [],
  "confirmation_opens_at": "2030-08-07T16:00:00Z",
  "confirmation_deadline_at": "2030-08-08T16:00:00Z",
  "checkin_opens_at": "2030-08-08T15:30:00Z",
  "checkin_closes_at": "2030-08-08T17:00:00Z",
  "checkin_radius_m": 150,
  "price_amount": null,
  "currency": null,
  "current_user_participation": null,
  "permissions": {
    "can_edit": false,
    "can_cancel": false,
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

### Confirmed response (200)

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
  "cancelled_at": null,
  "description": "Amatorski mecz siatkówki dla każdego chętnego.",
  "organizer": {
    "id": "bb1aedb3-54f4-45c4-ab10-2fb0a07b53ca",
    "display_name": "Organizer",
    "avatar_url": null
  },
  "tags": [],
  "confirmation_opens_at": "2030-08-07T16:00:00Z",
  "confirmation_deadline_at": "2030-08-08T16:00:00Z",
  "checkin_opens_at": "2030-08-08T15:30:00Z",
  "checkin_closes_at": "2030-08-08T17:00:00Z",
  "checkin_radius_m": 150,
  "price_amount": null,
  "currency": null,
  "current_user_participation": {
    "status": "CONFIRMED",
    "joined_at": "2030-08-01T12:00:00Z",
    "confirmed_at": "2030-08-07T16:00:00Z",
    "checked_in_at": null
  },
  "permissions": {
    "can_edit": false,
    "can_cancel": false,
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

### Checked-in response (200)

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
  "checked_in_count": 1,
  "waitlist_count": 0,
  "available_slots": 11,
  "status": "PUBLISHED",
  "cancelled_at": null,
  "description": "Amatorski mecz siatkówki dla każdego chętnego.",
  "organizer": {
    "id": "bb1aedb3-54f4-45c4-ab10-2fb0a07b53ca",
    "display_name": "Organizer",
    "avatar_url": null
  },
  "tags": [],
  "confirmation_opens_at": "2030-08-07T16:00:00Z",
  "confirmation_deadline_at": "2030-08-08T16:00:00Z",
  "checkin_opens_at": "2030-08-08T15:30:00Z",
  "checkin_closes_at": "2030-08-08T17:00:00Z",
  "checkin_radius_m": 150,
  "price_amount": null,
  "currency": null,
  "current_user_participation": {
    "status": "CHECKED_IN",
    "joined_at": "2030-08-01T12:00:00Z",
    "confirmed_at": "2030-08-07T16:00:00Z",
    "checked_in_at": "2030-08-08T15:45:00Z"
  },
  "permissions": {
    "can_edit": false,
    "can_cancel": false,
    "can_delete": false,
    "can_join": false,
    "can_leave": false,
    "can_confirm": false,
    "can_check_in": false,
    "can_view_gallery": false,
    "can_upload_photo": false
  }
}
```
