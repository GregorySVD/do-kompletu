# Activity waitlist contract

Migration `20261018_0009_add_activity_waitlist.py` follows verified head
`20261018_0008`. This defines the original FIFO milestone. Current 0010 adds an autonomous
[lifecycle worker](participation-lifecycle-worker.md): confirmation expiry, late
grace, and waitlist expiry at start. Notifications and frontend changes remain absent.

## Request and response

`POST /api/v1/activities/{activity_id}/join` keeps its access JWT, no-body request,
201 success, and full `ActivityRead` response. A non-organizer may request a place
only while `now < start_at`, using timezone-aware UTC evaluated after acquiring
the activity lock. Exact start and later return 409 `Activity has started`;
ended/cancelled activity conflicts retain their existing messages. This applies
to new joins and LEFT rejoins, whether capacity is available or full.

| Available capacity | Result |
| --- | --- |
| Unlimited | JOINED |
| Limited, active count below maximum | JOINED |
| Limited, active count at/above maximum | WAITLISTED |

Full capacity alone no longer returns `Activity is full`. Duplicate
JOINED/CONFIRMED/CHECKED_IN/WAITLISTED requests return the existing 409
`Already joined this activity`. COMPLETED/NO_SHOW remain terminal.

The existing frontend already declares `waitlist_count: number`, renders it on
limited activity detail, and reads `permissions.can_join` for its inactive Join
button. It has no WAITLISTED type, participation object, queue position, mutation
API/hooks, or waitlist section. My Activities still uses static joined/organized
IDs and fixtures. No frontend files were modified.

The current caller's queued participation is:

```json
{
  "status": "WAITLISTED",
  "joined_at": null,
  "waitlisted_at": "2030-08-01T12:05:00Z",
  "waitlist_position": 3,
  "confirmed_at": null,
  "checked_in_at": null,
  "completed_at": null,
  "no_show_at": null
}
```

Swagger includes complete JOINED, WAITLISTED, and promoted detail examples.
Previously returned fields and success codes remain. The participation object
adds nullable `waitlisted_at` and `waitlist_position`; `joined_at` becomes nullable
only for users who have no place. Existing active/final responses retain their
non-null join timestamps. LEFT remains null current participation. Anonymous,
unrelated, and organizer callers do not receive another user's state or position.
The public list exposes counts only, never a waitlist or private membership.

## Lifecycle, timestamps, and capacity

| State/transition | Meaning |
| --- | --- |
| WAITLISTED | A place was requested, no place obtained; cannot confirm/check in |
| WAITLISTED → JOINED | Synchronous FIFO promotion, without automatic confirmation |
| WAITLISTED → LEFT | Queue departure, no active capacity freed |
| LEFT → WAITLISTED | Reuse the same row, fresh queue-entry time, no join time |
| LEFT → JOINED | Reuse the same row, fresh active join time, clear queue timestamp |

`waitlisted_at` is entry time for the latest queue cycle. WAITLISTED requires it
and requires joined_at, left_at, confirmed_at, checked_in_at, completed_at, and
no_show_at to be null. Promotion preserves waitlisted_at and sets joined_at to
promotion time. Attendance timestamps remain null. Direct joins have no
waitlisted_at. Rejoining from LEFT clears all previous cycle timestamps and sets
only the timestamp appropriate for its new JOINED/WAITLISTED state. The retained
row describes the latest cycle; it is not an immutable audit log.

`joined_at` is nullable in the database so a queued person never receives a
misleading active join time. Its existing Python/server defaults remain available
for direct JOINED inserts; ORM explicit nulls are preserved. Every active/final
state requires joined_at. LEFT requires left_at and either a real joined_at, or
a waitlisted_at with no confirmed_at for someone who left without receiving a
place. All previous attendance-state CHECK requirements remain enforced.

`CAPACITY_CONSUMING_STATES` is still JOINED/CONFIRMED/CHECKED_IN.
`WAITLIST_STATES`, requested, leavable, visible, and attendance-history groups
separate these concepts centrally in the participation model. WAITLISTED never
enters active counts, joined relation, check-in counts, or finalization mappings.

- `participant_count`: SQL count of capacity-consuming states only.
- `waitlist_count`: SQL count of WAITLISTED only, including retained historical
  queues on direct detail/personal lists.
- `available_slots`: maximum minus active count; null for unlimited capacity.
- `checked_in_count`: unchanged CHECKED_IN + COMPLETED historical evidence.

## FIFO and transaction protocol

Both promotion and displayed position use the same canonical key:
`waitlisted_at ASC, user_id ASC`. UUID is the stable tie-breaker for equal times;
natural row order is never used. Position is the caller's SQL count of queued
rows whose key is less than or equal to their own key, hence 1-based. It is null
outside WAITLISTED. It is a snapshot and can change after another transaction.

Every join/rejoin/leave/edit/cancel writer locks the parent activity first with
`SELECT ... FOR UPDATE` under READ COMMITTED, refreshing cached activity and
participation state after waiting. No participation-first lock is introduced.
The shared `promote_waitlisted_participants` helper requires the caller to hold
that refreshed lock and flush pending changes. It never commits separately.

Before start, JOINED/CONFIRMED leave transitions the row to LEFT, flushes it,
counts actual free capacity, selects the earliest eligible queue users, and
promotes them in one SQL UPDATE before the response snapshot and commit. This
fills actual available capacity, including any previously unused places. A
response/projection failure rolls back both leave and promotion.

Leaving WAITLISTED never invokes promotion: no place was freed. Leave eligibility
remains uncancelled `now < end_at` for CONFIRMED/WAITLISTED. JOINED additionally
must precede its effective confirmation deadline to prevent expiry bypass;
CHECKED_IN and final states cannot leave. A leave at/after start may free capacity
but does not promote anyone, because admission has closed.

Organizer PATCH still requires both old and proposed start times in the future.
When capacity fields are edited, the helper uses the new maximum and actual
active count. Increasing 5 to 7 admits the earliest two waiters; changing to
unlimited admits all waiters. Capacity reductions still cannot evict active
participants or reduce the maximum below active count. Edit and promotion are
atomic. Cancellation winning serialization blocks any later leave/edit and
promotion; cancellation following a promotion preserves its committed evidence.

## Permissions and other endpoints

`can_join=true` means a non-organizer with no participation or LEFT can request a
place before start. It may return JOINED **or WAITLISTED**, even when full.
WAITLISTED has can_join/can_confirm/can_check_in=false and can_leave=true while
uncancelled and before end. Promotion restores normal JOINED permissions. Ended
and cancelled activities have all participant actions false.

Confirm/check-in for WAITLISTED return 409 `Not participating in this activity`
using the existing error convention. They never implicitly grant a place or
confirm a promoted person. The confirmation/check-in windows are unchanged.

`GET /api/v1/users/me/activities?relation=waitlisted&scope=upcoming` selects only
the caller's WAITLISTED records. It reuses the existing array, pagination, privacy,
and deterministic activity ordering. `relation=joined` excludes WAITLISTED.
All relations retain the same time rules: upcoming means `end_at > cutoff`
(including ongoing), history means `end_at <= cutoff`; omitted scope includes
both. Waitlisted upcoming therefore may include started but not-ended events.
No existing scope is silently redefined around start time.

Cancellation retains WAITLISTED/timestamps, keeps direct detail and personal
waitlisted listings with existing end-time scopes, and blocks every mutation.
Discovery still excludes cancelled activities. Finalization leaves WAITLISTED
unchanged: a person who never received a place becomes neither NO_SHOW nor
COMPLETED. An ended waitlist-only event has no unresolved attendance to finalize.

The lifecycle worker now expires overdue JOINED to CONFIRMATION_EXPIRED and
promotes FIFO waiters atomically before start. Each late promotion gets configured
grace from its real joined_at. At/after start, remaining WAITLISTED becomes
WAITLIST_EXPIRED and disappears from waitlist_count/relation=waitlisted. Both new
states are terminal and private on direct detail. Cancellation skips automation
and can retain its original historical waitlist. There is no notification/push;
see the lifecycle contract for polling and worker-lag semantics.

## Migration and downgrade

Upgrade adds nullable waitlisted_at, makes joined_at nullable, updates named
status/timestamp CHECKs, and adds the FIFO index. Existing rows, statuses, and
timestamps remain unchanged; old rows have waitlisted_at=null. The existing
primary key, CASCADE foreign keys, user index, and join default remain.

The index `(activity_id, status, waitlisted_at, user_id)` supports activity/status
counts and FIFO/range queries. A representative PostgreSQL test inserts 6,000
queued records in a rolled-back transaction, ANALYZEs the table, and verifies
EXPLAIN chooses `ix_activity_participations_fifo` for FIFO LIMIT without a Sort,
with no forced planner settings. This avoids scanning/sorting a whole large queue
just to promote its first users.

0008 cannot represent a queue and requires joined_at on every row. Downgrade
preserves records: WAITLISTED becomes inactive LEFT, left_at is downgrade time;
already-LEFT queue departures retain their real left_at. Only never-joined rows
receive their former waitlisted_at as legacy joined_at. This is a **lossy legacy
timestamp compromise**, not evidence that the user had an active place. It never
creates active membership, confirmation, check-in, or final attendance. Existing
active/final/previously-joined LEFT statuses and timestamps are unchanged.
Dropping waitlisted_at loses queue history, including promotion context. Upgrade
again does not recreate the old queue; inactive LEFT rows remain LEFT.

The isolated migration test runs 0008 → 0009 → 0008 → 0009 in its own generated
PostgreSQL/PostGIS database, validates existing data and all status/timestamp
constraints, and removes only that database. Development data is never downgraded
or deleted; no persistent volume is removed.

## Performance and frontend integration

Discovery remains one SELECT; authenticated detail and My Activities remain two
including authentication, independent of page/queue size. Counts, caller state,
and position are correlated SQL projections with eager organizer loading. No
participant collection is fetched to count or rank. Round trips are constant;
database work still scales with matching rows. Tests cover one/many activities,
two PostgreSQL time zones, FIFO ties and near ties, and rollback after promotion.

Frontend follow-up, without changes in this milestone:

1. Replace `current_user_participation: null` with the full object/null union,
   including WAITLISTED, nullable joined_at, waitlisted_at, and waitlist_position.
2. Add join/leave APIs/hooks. Treat 201 as either joined or queued based on returned
   status. Keep Join available when full if can_join is true; close it at start.
3. Render WAITLISTED, queue position, and a Leave waitlist action through the same
   DELETE endpoint. Hide confirmation/check-in controls while queued; promotion
   restores JOINED controls and still requires explicit confirmation.
4. Use the existing waitlist_count field as live data. Add a Waitlist section and
   real `relation=waitlisted` query, preserving pagination and cancelled context.
5. Scope personal/detail query caches to user identity; invalidate discovery,
   detail, joined/waitlisted/organized sections after join/leave/capacity edits and
   other mutations. Refresh on focus or explicit action to see other users' leaves
   and resulting promotion: this milestone adds no real-time push channel.
