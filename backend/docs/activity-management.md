# Organizer activity management

## Inspected frontend and baseline

The current frontend has no edit/cancel page, route, button, menu, API function, or
mutation hook. Activity details display the organizer but have no organizer-specific
controls. My Activities still uses mocks and section labels rather than lifecycle
badges. Its organized section includes all times; joined sections split by end time.
The existing ActivityStatus TypeScript union includes CANCELLED (and unused DRAFT),
but cards/details do not currently render cancellation status. Creation is already
integrated with a form/schema covering all editable public fields below.

No frontend files were changed. Future integration must add management actions and
forms, API/hooks, can_cancel/cancelled_at types, status rendering, mutation error
handling, and user-scoped query invalidation. The earlier membership-type and mock
integration gaps remain documented in the participation/My Activities contracts.

The management implementation started from a clean `backend` branch with
migration-file/database head `20261018_0004`. Its historical baseline verification
was 164 default tests and 20 separate PostgreSQL tests, with Ruff and lock validation
passing. That describes the start of implementation, not the current working-tree
status. Current migration-file/database head is `20261018_0007`; Compose uses host
port 5433. See the [README](../../README.md#testing) for the current combined checks.

## Persistent lifecycle and schema

Migration `20261018_0005_add_activity_cancellation.py`, parent `20261018_0004`, adds:

```sql
ALTER TABLE activities ADD COLUMN cancelled_at timestamptz NULL;
```

No old migrations, indexes, constraints, or membership columns change. Existing
rows start uncancelled. A nullable timestamp records the one new persistent fact
without duplicating time-derived state in an arbitrary status column.
That describes migration 0005. The subsequent [participation lifecycle](activity-participation.md)
adds status/left_at/confirmed_at in 0006 and the schedule/active-count rules below.
The [check-in contract](activity-check-in.md) adds 0007, CHECKED_IN/checked_in_at,
and stronger location protections without changing cancellation identity.

Status priority is deterministic:

1. cancelled_at is set: CANCELLED, even after end_at.
2. Otherwise, now >= end_at: ENDED.
3. Otherwise, now >= start_at: ONGOING.
4. Otherwise: PUBLISHED.

No DRAFT state, hard deletion, or uncancel operation is added. Detail/My Activities
reuse ActivityRead with additive nullable cancelled_at and permissions.can_cancel.
The public list keeps its existing shape; its status enum includes CANCELLED, but
cancelled events are excluded from discovery.

## PATCH contract

```http
PATCH /api/v1/activities/d54112d9-43cf-4986-8679-b6c236ac522c
Authorization: Bearer <organizer_access_token>
Content-Type: application/json

{
  "title": "Evening volleyball",
  "description": "A friendly volleyball match for all skill levels."
}
```

The response is 200 with the complete updated ActivityRead. Swagger has the full
text-edit response and selectable request examples for text, schedule, location,
capacity, unlimited participation, FREE-to-PAID, and PAID-to-FREE transitions.

Only the JWT-authenticated organizer may edit. Both the existing activity start and
the merged proposed start must be strictly in the future. Existing ongoing/ended
or cancelled activities cannot be edited; moving their dates cannot reactivate them.
This conservative policy avoids changing schedules, venue, or price during an event.
Additionally, actual changes to start_at or end_at return 409 while any
participation status is CONFIRMED or CHECKED_IN. Once anyone is CHECKED_IN, actual
latitude, longitude, location_name, and address changes also return 409. This keeps
the venue against which attendance was validated. Equivalent unchanged values are allowed,
as are other fields under normal management rules. LEFT rows with historical
confirmed_at do not block schedule changes. Editing never silently clears confirmations.

| Editable fields | Rules |
| --- | --- |
| title, description, location_name, address | Trimmed text with the existing creation length limits |
| category_id | Canonical category UUID from GET /api/v1/categories |
| start_at, end_at | Timezone-aware, normalized to UTC; end > start; merged start remains future |
| latitude, longitude | WGS 84 ranges; changing one preserves the other |
| min_participants | 2-100, no greater than finite maximum |
| has_participant_limit, max_participants | Finite max 2-100, at least minimum and active JOINED + CONFIRMED + CHECKED_IN count; LEFT excluded; null maximum for unlimited |
| price_type, price_amount | FREE/null or PAID/positive PLN amount with at most two decimal places |

Omitted fields stay unchanged. Unknown fields, organizer_id, status, cancelled_at,
internal counters/IDs, and empty objects return 422. Explicit null is allowed only
for max_participants and price_amount. The merged activity is validated with
ActivityCreate, so partial requests cannot bypass existing cross-field rules.

Transitions must explicitly supply consistent values:

```json
{
  "has_participant_limit": false,
  "max_participants": null
}
```

```json
{
  "has_participant_limit": true,
  "max_participants": 9
}
```

```json
{
  "price_type": "PAID",
  "price_amount": 25.5
}
```

```json
{
  "price_type": "FREE",
  "price_amount": null
}
```

The API does not implicitly clear omitted amounts/limits. Invalid merged price,
participant, category, coordinate, or time configuration returns 422. A finite
maximum below current membership is a state conflict and returns 409. No participant
is removed when changing limits.

## Cancellation contract and exact response

```http
POST /api/v1/activities/d54112d9-43cf-4986-8679-b6c236ac522c/cancel
Authorization: Bearer <organizer_access_token>
```

No body is needed. The organizer may cancel strictly before end_at, including while
ONGOING. Cancellation sets cancelled_at once, preserves the activity and all
memberships, and returns 200. A repeat returns 409 without changing the timestamp.
Example IDs/timestamps below are illustrative; the participant count belongs to
another user, because the organizer is separate from membership.

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
  "status": "CANCELLED",
  "cancelled_at": "2030-08-01T12:00:00Z",
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
    "can_join": false,
    "can_leave": false,
    "can_confirm": false,
    "can_check_in": false,
    "can_view_gallery": false,
    "can_upload_photo": false
  }
}
```

## Visibility, permissions, and errors

| Context | Cancelled behavior |
| --- | --- |
| Public discovery | Excluded before sorting/pagination, including filtered requests |
| Direct detail | Still available; CANCELLED and cancelled_at are public |
| Organized My Activities | Retained, with null organizer membership |
| Joined My Activities | Retained for caller's JOINED/CONFIRMED/CHECKED_IN state; LEFT excluded |
| Upcoming/history | Still split strictly by end_at; future cancelled activities remain upcoming; after end they are history with CANCELLED status |
| Counts/capacity | Reflect all active membership including CHECKED_IN, excluding LEFT; checked_in_count is real, waitlist stays zero; cancelled places are not bookable |
| Join, leave, confirm, and check-in | All return 409 after cancellation, preserving every status/timestamp including checked_in_at |
| Private state | Anonymous/unrelated callers receive null membership, never someone else's state |

For uncancelled activities, organizer can_edit is true before start and can_cancel
is true before end. Participant can_join/can_leave follow active state and lifecycle;
CHECKED_IN cannot leave. can_check_in permits an attempt, still requiring PostGIS validation.
Every cancelled permission is false. can_delete and all future permissions remain
false. The UI must render status rather than infer bookability from remaining slots.

| Status | Exact detail or meaning |
| --- | --- |
| 401 | Missing/invalid/expired access JWT, refresh JWT used as access, or inactive user |
| 403 | `{"detail":"Only the organizer can manage this activity"}` |
| 404 | `{"detail":"Activity not found"}` |
| 409 | `{"detail":"Activity is cancelled"}` for management/participant operations after cancellation |
| 409 | `{"detail":"Activity can only be edited before it starts"}` |
| 409 | `{"detail":"Activity has ended"}` for cancellation at/after end |
| 409 | `{"detail":"Participant limit cannot be below current participant count"}` |
| 409 | `{"detail":"Cannot change schedule while participants are confirmed"}` |
| 409 | `{"detail":"Cannot change location after participants have checked in"}` |
| 422 | Standard validation details for input/merged configuration; `{"detail":"start_at must remain strictly in the future"}` for a proposed nonfuture start |

Normal validation can reject malformed input before ownership lookup. After valid
input/authentication, checks run as existence, ownership, cancellation, then the
applicable time/capacity rules. Errors expose no owner ID or database details.
Management responses use Cache-Control: private, no-store.

## Transactions, query efficiency, and migration validation

Management, join, leave, confirm, and check-in all use get_activity_for_update: a parent-only SELECT
FOR UPDATE with populate_existing, under explicit PostgreSQL READ COMMITTED.
Lifecycle checks use a UTC cutoff captured after waiting for the lock. PATCH reads
the locked activity projection, merges only supplied fields, validates merged state
and current membership, flushes, reads the updated projection, and commits. Cancel
sets its timestamp, flushes, reads the projection, and commits. Failures roll back.
The lock is held through the response snapshot; another transaction may naturally
change state after commit.

Serial outcomes are defined and tested in both lock orders:

- Capacity reduction first: join sees the smaller capacity and fails if full.
- Join first: unsafe reduction sees the new count and fails with 409.
- Cancellation first: a later join fails; no membership is inserted after it wins.
- Join first: join may succeed, then cancellation preserves that membership.
- Independent organizer updates merge against refreshed state, preserving omitted fields.
- Cancel before edit blocks it; edit before cancel can succeed, followed by cancellation.

SQL round trips are constant, not per participant: authenticated PATCH has four
SELECTs (auth, lock, pre-update projection, returned projection); cancellation has
three (auth, lock, returned projection), plus the applicable UPDATE. Counts and
caller state remain correlated projections with organizer eager-loading. Public
discovery stays one SELECT, My Activities two including auth. PostgreSQL tests
verify these paths and actual PostGIS coordinate updates.

The migration was validated in a new temporary PostGIS database through
0004 -> 0005 -> 0004 -> 0005. A cancelled activity with membership was seeded before
downgrade; user, activity, and membership rows survived both directions. Downgrade
removes cancellation metadata, so re-upgraded rows are uncancelled. This is a
destructive metadata rollback and should not be applied to real data without a
backup/reviewed rollback plan. The normal development database was only upgraded;
the temporary database was removed, with no persistent volume deletion.

### Management implementation verification record

The results below record implementation validation, including the temporary
database migration cycle and data snapshot at that time. The documentation update
reruns the combined tests/checks in [the README](../../README.md#testing); it does
not repeat downgrade probes against development data.

| Check | Result |
| --- | --- |
| `uv run pytest -v` | 246 passed; 32 environment-gated PostgreSQL tests skipped |
| Separate PostgreSQL run across all four integration modules | 32 passed |
| New concurrency scenarios | Eight passed, forcing both lock orders for each of four scenarios |
| `uv run ruff check .` | Passed |
| `uv run python -m compileall app` | Passed |
| `uv lock --check` | Passed; lockfile unchanged |
| `uv run alembic current` | `20261018_0005 (head)` in the development database |
| Upgrade/downgrade/re-upgrade | Passed in temporary PostgreSQL/PostGIS, including activity/membership preservation |
| Complete JSON documentation examples | Matched to API examples in all three contract documents |
| Database cleanup | One existing user, zero activities/memberships after tests |
| `git diff --check` | Passed |
| Frontend diff | Empty |

94 new test cases were added: 81 isolated management cases, 12 PostgreSQL cases,
and one OpenAPI contract case. Existing organizer-permission assertions were updated
for implemented edit/cancel actions while retaining checks that unsupported actions
stay false. The normal test runs retain the existing TestClient/httpx deprecation
and local pytest-cache permission warnings. The standalone migration reflection
probe also reported unregistered geography reflection warnings; real PostGIS
round-trip/update tests passed. No warnings were suppressed.

## Remaining work and limits

Frontend integration can reuse create-form controls with partial-update handling.
It still needs edit/cancel API functions and mutation hooks, lifecycle/cancelled_at display,
honor permissions, and invalidate discovery/detail/personal caches after mutations.
My Activities still needs its previously documented replacement of mock arrays.
Access-token refresh and authentication-specific query keys remain frontend work.
Confirmation needs frontend API/hooks/UI as well, reusing existing can_confirm and
confirmation timing fields. Check-in needs browser geolocation, API/hooks, state/
error handling, and cache refresh too; its passive timing panel already exists.

There is no hard deletion, DRAFT, uncancel, cancellation reason, edit audit/version
token, notifications, or payment/refund processing. Writes to the same field use
the last successful writer. Editing a field does not notify participants. Attendance,
waitlist, completed attendance/no-show, reviews, XP, ranks, achievements,
chat, and media remain unimplemented. Timed attendance confirmation and retained
JOINED/CONFIRMED/CHECKED_IN/LEFT and timed PostGIS check-in are implemented. The next
backend milestone can define completed attendance/no-show and cancelled-event policies.
