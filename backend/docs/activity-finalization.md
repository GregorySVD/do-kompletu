# Final attendance outcomes

## Explicit lifecycle

The activity remains time-derived ENDED at `now >= end_at`. COMPLETED and NO_SHOW
are persisted **participation** outcomes, never new Activity statuses.

| Participation | Meaning | Consumes capacity | Finalization result |
| --- | --- | --- | --- |
| JOINED | Unresolved participation without confirmation | Yes | NO_SHOW |
| CONFIRMED | Unresolved participation with self-declared intent | Yes | NO_SHOW |
| CHECKED_IN | Time and PostGIS proximity checks succeeded | Yes | COMPLETED |
| COMPLETED | Successful checked-in attendance explicitly resolved after end | No | Unchanged |
| NO_SHOW | Unresolved JOINED/CONFIRMED attendance resolved without check-in | No | Unchanged |
| LEFT | Voluntary withdrawal from the latest participation cycle | No | Unchanged |

The model centralizes capacity/current/final/history/check-in status groups;
participation_rules centralizes the finalization mapping. Final outcomes are
terminal: join/rejoin, leave, confirm, and check-in cannot change them. There is
no manual attendance override or undo. Existing ended editing/cancellation rules
remain in force.

The participation lifecycle worker automates expiry/promotion only. Explicit finalization fits
the existing organizer management API, is deterministic, and makes the write and
its transaction visible. Reaching end_at alone does not mutate participation.
An organizer who never finalizes leaves unresolved states in history. COMPLETED
is suitable for future attendance XP/review authorization; this milestone awards
no points and implements no reviews, rewards, ranks, or achievements.

## Endpoint and failures

```http
POST /api/v1/activities/{activity_id}/finalize
Authorization: Bearer <organizer_access_token>
```

No request body or participant IDs are needed. The endpoint uses the current
active user's access JWT and the activity's persisted organizer ID. Refresh JWTs
are not accepted. It returns the existing ActivityRead shape, with no new wrapper.
Responses use `Cache-Control: private, no-store`.

| Status | Exact detail / result |
| --- | --- |
| 200 | Updated ActivityRead; normally null organizer membership and can_finalize=false |
| 401 | Existing missing/invalid/expired/refresh-token or unavailable-user errors |
| 403 | Only the organizer can manage this activity |
| 404 | Activity not found |
| 409 | Activity is cancelled |
| 409 | Activity can only be finalized after it ends |
| 409 | No unresolved attendance to finalize |
| 422 | Standard FastAPI validation details for malformed activity UUID |

After authentication/path validation, checks run in this order: lock/load activity,
existence, ownership, cancellation, time, unresolved-row update. Time is captured
after waiting for the lock. All domain errors use `{"detail":"message"}` and
roll back. The exact UTC boundary is inclusive: end minus one microsecond fails;
exact end and later succeed when unresolved rows exist.

Repeat requests return 409 when no JOINED/CONFIRMED/CHECKED_IN rows remain.
Empty or LEFT-only attendance has the same response. The operation is idempotent
at the data level: repeats never change final timestamps. Existing final rows
are excluded even when other unresolved rows still need finalization. There is no
Activity.finalized_at marker; eligibility derives from participation states.

## Cancellation and boundary races

Cancelled activities cannot use this endpoint, even after their planned end.
CONFIRMED, CHECKED_IN, LEFT, and all previous timestamps remain evidence of state
at cancellation. No CANCELLED_PARTICIPATION state or automatic NO_SHOW conversion
is invented. Future refund/reward policy must interpret cancelled events separately.

Every attendance/management writer first refreshes and locks the same activity
row with SELECT FOR UPDATE under PostgreSQL READ COMMITTED. Finalization holds
that lock through validation, one bulk CASE UPDATE, response projection, and
commit. Failure rolls back the entire update. Existing writers refresh cached
membership state after acquiring the parent lock.

Check-in closes exclusively at min(start + configured duration, end_at), so it
is already forbidden at exact end. If a valid check-in just before end wins the
lock, finalization sees CHECKED_IN and produces COMPLETED. If finalization wins
at end, a later check-in fails and NO_SHOW cannot be revived. Cancellation before
end may win and preserve unresolved evidence; after finalization, cancellation
fails under the existing ended rule. Join/leave/confirm obey the same serialization
and existing timing restrictions.

## Counts, history, permissions, and privacy

participant_count retains its established active capacity meaning:
JOINED + CONFIRMED + CHECKED_IN, excluding the organizer and final/LEFT states.
It becomes zero after all unresolved rows are finalized. Finite available_slots
is still max minus this count (therefore the full maximum); unlimited is null.
Ended activities remain unjoinable regardless of those numbers. This field is
not a historical attendance total.

checked_in_count counts CHECKED_IN + COMPLETED, so finalizing successful attendance
does not erase the public count of people who checked in. No completed_count,
no_show_count, participant roster, or other public attendance analytics is added.
waitlist_count counts retained WAITLISTED rows. Finalization never converts them
to COMPLETED/NO_SHOW: they had no place. The lifecycle worker expires remaining
queues at start, except cancelled activities. Both CONFIRMATION_EXPIRED and
WAITLIST_EXPIRED are excluded from finalization transitions; see the
[worker contract](participation-lifecycle-worker.md).

Joined My Activities uses current JOINED/CONFIRMED/CHECKED_IN states before end,
and those unresolved states plus COMPLETED/NO_SHOW at/after end. LEFT is always
excluded; final states never appear in upcoming. The existing array, pagination,
sorting, UTC cutoff, cancellation visibility, and organized relation are retained.

Direct detail and My Activities expose only the caller's state and timestamps:
joined_at, nullable confirmed_at, checked_in_at, completed_at, and no_show_at.
NO_SHOW retains confirmed_at only if confirmation really happened. Anonymous,
unrelated, LEFT, and normal organizer callers have null participation. There is
no way to request another user's state. Personalized reads retain private/no-store
and Vary: Authorization.

can_finalize is true only for the authenticated organizer of an uncancelled
ENDED activity with unresolved attendance. COMPLETED/NO_SHOW have false can_join,
can_leave, can_confirm, and can_check_in. Cancelled activity permissions are all
false. Existing can_edit/can_cancel lifecycle rules remain. These flags guide UI;
the server still enforces every rule.

## Migration and evidence

`20261018_0008_add_final_attendance_outcomes.py` follows verified 0007. It adds
nullable completed_at and no_show_at TIMESTAMPTZ columns and replaces the status
and state/timestamp CHECKs. No existing row/status/timestamp, key, index, or foreign
key is changed by upgrade.

This table describes migration 0008. Current 0009 additionally supports WAITLISTED
with only waitlisted_at, and LEFT with waitlisted_at/left_at but no joined_at when
the user never received a place. Active/final requirements below are unchanged.

| State | Required timestamps | Required nulls |
| --- | --- | --- |
| JOINED | joined_at | left_at, confirmed_at, checked_in_at, completed_at, no_show_at |
| CONFIRMED | joined_at, confirmed_at | left_at, checked_in_at, completed_at, no_show_at |
| CHECKED_IN | joined_at, confirmed_at, checked_in_at | left_at, completed_at, no_show_at |
| COMPLETED | joined_at, confirmed_at, checked_in_at, completed_at | left_at, no_show_at |
| NO_SHOW | joined_at, no_show_at | left_at, checked_in_at, completed_at; confirmed_at optional |
| LEFT | joined_at, left_at | checked_in_at, completed_at, no_show_at; confirmed_at optional |

One UTC time, evaluated after the parent lock, is used for every newly resolved
row. completed_at/no_show_at record when finalization ran, not the event end or
physical check-in time. Earlier joined_at/confirmed_at/checked_in_at remain intact.

Downgrade maps COMPLETED to CHECKED_IN and drops the two final-only columns.
NO_SHOW with confirmed_at becomes CONFIRMED; without it, NO_SHOW becomes JOINED.
Unconditional NO_SHOW to CONFIRMED would violate the old constraint or require
fabricating confirmation evidence for originally JOINED users, so the mapping is
deliberately conditional. All rows and older timestamps survive. Re-upgrade
preserves those restored states with null final timestamps; final outcomes must
be explicitly resolved again if needed.

The complete 0007 -> 0008 -> 0007 -> 0008 cycle is tested in a generated temporary
PostgreSQL/PostGIS database, including all four previous states, both NO_SHOW
origins, COMPLETED, invalid constraints, keys, and exact old timestamp preservation.
Only that generated database is dropped. The development database is only upgraded;
no persistent Docker volume is deleted.

## Verification and frontend work

The baseline was rerun before edits: 355 default tests and 81 separate PostgreSQL
tests passed, with file/database head 0007. New isolated tests cover authorization,
all transitions, boundaries, constraints, rollback, counts, privacy, history,
terminal mutations, and OpenAPI. Real PostgreSQL tests force both observed parent
lock orders for finalize versus check-in, finalize, cancel, join, leave, and confirm.
Thread-local controlled UTC clocks and observed lock waiters avoid wall-clock sleeps.
Positive/negative database time zones and real PostGIS check-in are covered.

Finalization uses two service SELECTs (lock and response), three including HTTP
authentication, plus one UPDATE for 1 or 120 participants in PostgreSQL tests.
The isolated bulk test also covers 1 and 80 participants. Public discovery remains
one SELECT and authenticated detail/My Activities two; no participant collections
or N+1 queries are introduced. Database work grows with matching rows; constant
round trips do not imply constant CPU time. Current combined validation is in the
[README](../../README.md#testing).

Frontend source was inspected and unchanged. The Activity type still fixes
current_user_participation to null, My Activities uses static fixtures, and detail
has a passive check-in panel with no mutation integration. No COMPLETED/NO_SHOW or
finalization UI exists. Add the five-state membership/null union and final timestamps,
can_finalize/can_cancel/cancelled_at, real user-scoped history queries, caller outcome
badges, organizer finalize API/hook/action, pending/result/error states, and
discovery/detail/personal query invalidation after finalization. Keep Activity ENDED
separate from participation COMPLETED and avoid displaying participant_count as
historical attendance. Future review/XP UI must wait for actual product/API support;
the existing profile only displays points_total.

Limits remain: no automatic attendance finalization, manual override, undo, immutable attendance audit log,
rewards/reviews, cancelled-event refund policy, or GPS anti-spoofing. The next
practical milestone is frontend integration of the implemented lifecycle; a later
backend milestone can define review/XP eligibility and duplicate protection using
COMPLETED as the authoritative successful outcome.

## Complete response examples

### Organizer finalization response (200)

An ended activity with one checked-in participant finalized to COMPLETED. The
organizer receives no other user's membership. These examples are inside the
72-hour [gallery window](activity-gallery.md): organizer view-only, COMPLETED
view/upload, NO_SHOW neither.

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
  "checked_in_count": 1,
  "waitlist_count": 0,
  "available_slots": 12,
  "status": "ENDED",
  "cancelled_at": null,
  "description": "Amatorski mecz siatkówki dla każdego chętnego.",
  "organizer": {
    "id": "bb1aedb3-54f4-45c4-ab10-2fb0a07b53ca",
    "display_name": "Organizer",
    "avatar_url": null
  },
  "tags": [],
  "confirmation_opens_at": "2030-08-08T15:00:00Z",
  "confirmation_deadline_at": "2030-08-08T15:30:00Z",
  "checkin_opens_at": "2030-08-08T15:30:00Z",
  "checkin_closes_at": "2030-08-08T17:00:00Z",
  "checkin_radius_m": 150,
  "price_amount": null,
  "currency": null,
  "current_user_participation": null,
  "permissions": {
    "can_edit": false,
    "can_cancel": false,
    "can_finalize": false,
    "can_delete": false,
    "can_join": false,
    "can_leave": false,
    "can_confirm": false,
    "can_check_in": false,
    "can_view_gallery": true,
    "can_upload_photo": false
  }
}
```

### Caller completed detail/history

The participant's own subsequent GET detail (or item in joined history):

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
  "checked_in_count": 1,
  "waitlist_count": 0,
  "available_slots": 12,
  "status": "ENDED",
  "cancelled_at": null,
  "description": "Amatorski mecz siatkówki dla każdego chętnego.",
  "organizer": {
    "id": "bb1aedb3-54f4-45c4-ab10-2fb0a07b53ca",
    "display_name": "Organizer",
    "avatar_url": null
  },
  "tags": [],
  "confirmation_opens_at": "2030-08-08T15:00:00Z",
  "confirmation_deadline_at": "2030-08-08T15:30:00Z",
  "checkin_opens_at": "2030-08-08T15:30:00Z",
  "checkin_closes_at": "2030-08-08T17:00:00Z",
  "checkin_radius_m": 150,
  "price_amount": null,
  "currency": null,
  "current_user_participation": {
    "status": "COMPLETED",
    "joined_at": "2030-08-01T12:00:00Z",
    "confirmed_at": "2030-08-08T15:05:00Z",
    "checked_in_at": "2030-08-08T15:45:00Z",
    "completed_at": "2030-08-08T18:00:00Z",
    "no_show_at": null
  },
  "permissions": {
    "can_edit": false,
    "can_cancel": false,
    "can_finalize": false,
    "can_delete": false,
    "can_join": false,
    "can_leave": false,
    "can_confirm": false,
    "can_check_in": false,
    "can_view_gallery": true,
    "can_upload_photo": true
  }
}
```

### Caller no-show detail/history

A separate activity with an originally JOINED participant and no check-in:

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
  "status": "ENDED",
  "cancelled_at": null,
  "description": "Amatorski mecz siatkówki dla każdego chętnego.",
  "organizer": {
    "id": "bb1aedb3-54f4-45c4-ab10-2fb0a07b53ca",
    "display_name": "Organizer",
    "avatar_url": null
  },
  "tags": [],
  "confirmation_opens_at": "2030-08-08T15:00:00Z",
  "confirmation_deadline_at": "2030-08-08T15:30:00Z",
  "checkin_opens_at": "2030-08-08T15:30:00Z",
  "checkin_closes_at": "2030-08-08T17:00:00Z",
  "checkin_radius_m": 150,
  "price_amount": null,
  "currency": null,
  "current_user_participation": {
    "status": "NO_SHOW",
    "joined_at": "2030-08-01T12:00:00Z",
    "confirmed_at": null,
    "checked_in_at": null,
    "completed_at": null,
    "no_show_at": "2030-08-08T18:00:00Z"
  },
  "permissions": {
    "can_edit": false,
    "can_cancel": false,
    "can_finalize": false,
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
