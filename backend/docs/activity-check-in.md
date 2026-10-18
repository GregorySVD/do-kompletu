# Activity check-in contract

## Scope and compatibility

`POST /api/v1/activities/{activity_id}/check-in` extends the existing
[participation lifecycle](activity-participation.md). It requires an access JWT and
CONFIRMED non-organizer membership. It returns full ActivityRead on success (200),
transitioning CONFIRMED → CHECKED_IN. JOINED is never implicitly confirmed.
CHECKED_IN is active and consumes the same place; LEFT remains inactive.

```json
{"latitude": 52.4232, "longitude": 16.9461}
```

Both coordinates are required, finite WGS 84 numbers with the existing creation
ranges: latitude −90..90 and longitude −180..180. Unknown fields are rejected.
The organizer cannot check in merely because they own the activity.

## Window and public metadata

| Setting | Default | Valid values |
| --- | --- | --- |
| ACTIVITY_CHECK_IN_OPEN_MINUTES_BEFORE | 30 | Integer 0–525600 |
| ACTIVITY_CHECK_IN_CLOSE_MINUTES_AFTER | 60 | Integer 0–525600 |
| ACTIVITY_CHECK_IN_RADIUS_METERS | 150 | Integer 1–100000 |

Settings are listed in backend/.env.example. The shared participation_rules helper
derives UTC timing without persisted window columns:

```text
opens = start_at - configured open-before minutes
deadline = min(start_at + configured close-after minutes, end_at)
allowed exactly when opens <= now < deadline
```

The opening is inclusive; the deadline and activity end are exclusive. Both minute
settings may be zero; zero/zero defines an empty window. Arithmetic at extreme
supported dates saturates at the representable UTC datetime boundary.

Existing public ActivityRead fields are reused: `checkin_opens_at`,
`checkin_closes_at` (the deadline), and `checkin_radius_m`. These names preserve the
frontend contract; no duplicate `check_in_*` timing fields are added. Metadata is
nominal and remains readable after cancellation/end. Discovery's shape is unchanged.

`permissions.can_check_in` means authenticated CONFIRMED non-organizer state and
time/lifecycle allow an **attempt**. It cannot know the user's location before POST.
The endpoint must still validate proximity. CHECKED_IN cannot join, leave, confirm,
or check in again. There is no undo check-in.

## Authoritative proximity and privacy

The service acquires the existing activity-row lock, validates state/time, then
executes PostGIS `ST_DWithin(activity.location, submitted_geography, radius, true)`.
The submitted point is built as `ST_MakePoint(longitude, latitude)`, SRID 4326,
cast to Geography. Geography uses meters and spheroidal distance; see the
[official ST_DWithin contract](https://postgis.net/docs/ST_DWithin.html).
There is no degree conversion, Euclidean shortcut, or Python Haversine fallback.
An unsupported non-PostgreSQL database returns 503 rather than authorizing proximity.

The radius rule is inclusive (`distance <= radius`) as evaluated by PostGIS,
subject to floating-point/geodesic precision. Tests construct real geodesic points
with [ST_Project](https://postgis.net/docs/ST_Project.html), including points 0.01 m
inside/outside the 150 m radius; they do not rely on fragile exact-float equality.
Coordinate ordering and crossing the date line are tested independently.

Only checked_in_at is persisted. Submitted coordinates and computed distance are
not stored or returned. The activity's public venue coordinates remain public.
Current-user participation adds nullable checked_in_at beside joined_at/confirmed_at;
only the caller's active timestamps are exposed. Anonymous/unrelated/LEFT callers
receive null participation. Aggregate checked_in_count and nominal timing/radius
are public. Responses use the existing private/no-store cache policy.

The server validates submitted coordinates, **not the authenticity of device GPS**.
Clients can spoof coordinates. This milestone provides no anti-spoofing/device
attestation and makes no fraud-proof attendance claim.

## State, counts, management, and cancellation

- Success preserves joined_at/confirmed_at and sets checked_in_at once. Repeated
  POST returns 409 without changing it. No second participation row is created.
- `participant_count`/available_slots use centralized JOINED, CONFIRMED, CHECKED_IN
  active states. checked_in_count counts only CHECKED_IN; waitlist_count stays zero.
- JOINED/CONFIRMED can leave under the existing uncancelled/before-end rule.
  CHECKED_IN cannot leave. LEFT rejoin resets joined_at and clears all lifecycle
  timestamps, including checked_in_at, for the new JOINED cycle.
- Joined My Activities includes CHECKED_IN, excludes LEFT, and keeps the existing
  end-time upcoming/history scopes. History preserves CHECKED_IN; no separate
  attendance-history endpoint is introduced.
- Schedule changes remain blocked while any participant is CONFIRMED or CHECKED_IN.
  Once any participant is CHECKED_IN, actual latitude/longitude/location_name/address
  changes also return 409. Equivalent unchanged values and other safe edits remain
  possible while normal management lifecycle rules allow editing.
- Cancellation before end can preserve CHECKED_IN/checked_in_at, with CANCELLED
  activity status and all action permissions false. No participation state is
  rewritten. Future completion/reward policy for cancelled events is undecided.

See [management](activity-management.md) and [My Activities](my-activities.md) for
the unchanged ownership, pagination, and visibility contracts.

## Errors

Domain errors use `{"detail":"message"}`. After normal payload/auth validation,
the service checks existence, organizer, cancellation, end time, membership/status,
window, then proximity. Time/state are read after acquiring the parent lock.

| Status | Exact detail / meaning |
| --- | --- |
| 401 | Existing missing/invalid/expired/refresh-token or unavailable-user errors |
| 404 | Activity not found |
| 409 | Organizer cannot check in to their own activity |
| 409 | Not participating in this activity (no row or LEFT) |
| 409 | Attendance must be confirmed before check-in (JOINED) |
| 409 | Already checked in |
| 409 | Activity is cancelled |
| 409 | Activity has ended |
| 409 | Check-in window has not opened |
| 409 | Check-in window has closed |
| 409 | Outside check-in radius |
| 409 | Checked-in participants cannot leave (DELETE join) |
| 409 | Cannot change location after participants have checked in (PATCH) |
| 422 | Standard validation details for invalid UUID/body/coordinates |
| 503 | Check-in requires PostgreSQL/PostGIS (no approximate fallback) |

Failed check-in rolls back without changing status or timestamps. Confirming a
CHECKED_IN record returns Already checked in; joining it returns the existing
Already joined this activity conflict.

## Migration and concurrency validation

`20261018_0007_add_participation_check_in.py`, parent `20261018_0006`, adds nullable
TIMESTAMPTZ checked_in_at and replaces the two lifecycle CHECK constraints. Existing
JOINED/CONFIRMED/LEFT data is unchanged. CHECKED_IN requires confirmed_at and
checked_in_at, with null left_at; other states require null checked_in_at.
The primary key, foreign keys, and existing indexes remain.

Downgrade maps CHECKED_IN back to CONFIRMED, preserves joined_at/confirmed_at and
all participation rows, then drops checked_in_at and restores the old CHECKs.
Check-in evidence is lost; no participation history is deleted by 0007 downgrade.
Re-upgrade leaves converted rows CONFIRMED with null checked_in_at. The full
0006 → 0007 → 0006 → 0007 cycle is tested only in a generated temporary PostGIS
database, which is removed afterward. Normal development data is only upgraded.

Check-in follows the same activity-first FOR UPDATE protocol as every other
writer under READ COMMITTED. Cached activity/membership state is refreshed after
waiting. PostGIS validation and the returned snapshot occur while the lock is held.
Both observed lock orders are tested for duplicate check-in, leave, cancel,
location edit, time edit, and confirm. A location edit that wins first changes the
location against which check-in is validated; a check-in that wins blocks that edit.

SQL projections count active and checked-in states without loading participant
collections. Discovery remains one SELECT, authenticated detail/My Activities two,
PATCH four, and cancel three. Check-in has four SELECTs in the service (lock,
membership, PostGIS, returned projection), five including HTTP authentication.
Existing multiple-item query-count regressions remain in place. Isolated tests
stub proximity and test domain behavior only; real PostGIS tests establish spatial
behavior. Current combined test/check results are in the [README](../../README.md#testing).

## Frontend work and remaining scope

The current frontend already declares checkin_* metadata, checked_in_count, and
can_check_in, and details render a passive timing/radius panel. It has no browser
geolocation utility, check-in API/mutation, action button, or CHECKED_IN membership
union. The existing membership type remains exactly null; My Activities is mocked.

Add the active participation union and checked_in_at, browser permission/coordinate
flow, timeout/denial/unavailable-location handling, mutation/pending/success UI,
outside-radius/window error handling, and permission-driven actions. Refresh
discovery/detail/personal caches after check-in and scope personalized keys to
identity. Retain the existing checkin_* field names. No frontend files were changed.

COMPLETED, NO_SHOW, automatic completion, rewards, reviews, waitlists, QR/NFC,
notifications, media, payment/refund, exact participant-location history, and a
full participation event log remain unimplemented.

## Complete successful response

Illustrative IDs/date and default settings; Swagger provides the same full example.

<!-- full-response -->

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
