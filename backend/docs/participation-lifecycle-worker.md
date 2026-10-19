# Automated participation lifecycle

Revision `20261019_0010` follows verified `20261018_0009`. The API uses synchronous
SQLAlchemy sessions. Previously confirmation opened 24 hours before start and
closed at start, waitlist promotion happened only on active leave/capacity edits,
and no application lifespan worker existed. This milestone adds autonomous
reservation expiry and FIFO promotion, without automatic activity finalization.

## Configuration and deadlines

| Environment variable | Default | Validation |
| --- | --- | --- |
| ACTIVITY_CONFIRMATION_OPEN_MINUTES_BEFORE | 60 | Positive integer, at most 525600 |
| ACTIVITY_CONFIRMATION_DEADLINE_MINUTES_BEFORE | 30 | Nonnegative integer, strictly below opening offset |
| ACTIVITY_LATE_CONFIRMATION_GRACE_MINUTES | 10 | Positive integer, at most 525600 |
| PARTICIPATION_LIFECYCLE_WORKER_ENABLED | true | Boolean |
| PARTICIPATION_LIFECYCLE_SWEEP_INTERVAL_SECONDS | 60 | Finite positive number |

Replace the old `ACTIVITY_CONFIRMATION_WINDOW_HOURS` key in local configuration;
that setting has been removed. The settings model's existing extra-field policy
ignores unrecognized environment keys. `.env.example` documents the new keys;
the developer's private `.env` is not rewritten. Restart the application after
configuration changes. Normal tests explicitly disable the worker before app
construction; worker tests enable it for their own app instances.

All calculations use aware UTC. Opening is `start_at - open_minutes`; the public
normal deadline is `start_at - deadline_minutes`. The existing top-level
`confirmation_opens_at` and `confirmation_deadline_at` retain public,
caller-independent meanings. The latter now represents the normal deadline,
rather than start itself. Configuration requires `open > deadline >= 0`.

The central `effective_confirmation_deadline(start_at, joined_at)` rule is:

```text
if joined_at < normal_deadline:
    deadline = normal_deadline
else:
    deadline = min(joined_at + configured_grace, start_at)
```

`joined_at` means actual place acquisition, including promotion; `waitlisted_at`
continues to mean queue entry. This formula covers direct joins, eligible LEFT
rejoins, and the existing centralized promotion helper. No redundant deadline
column or event log is stored. Schedule edits recalculate timing, retain FIFO
order, and keep the existing CONFIRMED/CHECKED_IN restrictions.

Example, start 18:00, default configuration:

| Event | Result |
| --- | --- |
| Early member at 16:59:59 | Confirmation unavailable |
| Early member at 17:00:00 | Confirmation available |
| Early member at 17:29:59.999999 | Confirmation available |
| Early member at 17:30:00 | Confirmation closed; due for system expiry |
| Place acquired at 17:30:00 | Effective deadline 17:40:00 |
| That member at 17:39:59.999999 | Confirmation available |
| That member at 17:40:00 | Closed; due for expiry and next FIFO round |
| Place acquired at 17:55:00 | Deadline capped at 18:00:00 |
| Exactly 18:00:00 | No join/rejoin, confirmation, or promotion; waitlist due to expire |

The strict formula also means a place acquired just **before** the normal deadline
has only the remaining normal window, even if very short. Grace begins for joins
at or after that deadline; tests explicitly cover this boundary.

## States, integrity, counts, and privacy

| New state | Meaning and evidence |
| --- | --- |
| CONFIRMATION_EXPIRED | Former JOINED reservation released automatically. joined_at retained; confirmation_expired_at is the actual UTC sweep time. waitlisted_at retained if promoted earlier. No confirmation/check-in/final attendance/left timestamps. |
| WAITLIST_EXPIRED | Still queued when start was reached. waitlisted_at retained, joined_at remains null, waitlist_expired_at is the actual UTC sweep time. No attendance/left timestamps. |

Both states are terminal for that activity and are separate from voluntary LEFT.
They cannot join/rejoin, leave, confirm, or check in. Expiry timestamps describe
when the sweep persisted the change, not a backdated deadline. Existing states
must have null expiry timestamps. Named database CHECKs enforce these rules;
status is widened from VARCHAR(16) to VARCHAR(24) for CONFIRMATION_EXPIRED.
Existing keys, defaults, attendance constraints, and FIFO indexes remain intact.

`participant_count` remains JOINED + CONFIRMED + CHECKED_IN. `waitlist_count`
remains WAITLISTED only; checked_in_count remains CHECKED_IN + COMPLETED.
Expired states consume no capacity and count in neither queue nor attendance.
Counts reflect persisted state: an overdue JOINED row may still count until the
next successful sweep. Request-time permissions never grant overdue confirmation.

Direct authenticated detail exposes the caller's expired state, joined_at,
waitlisted_at, and nullable expiry timestamps, with every participant action
false. It exposes `effective_confirmation_deadline_at` only for JOINED, otherwise
null. This avoids presenting a recalculated deadline as historical evidence after
a later schedule edit. LEFT remains null current participation. Anonymous and
unrelated users receive no other person's state/timestamps. Public discovery
contains counts only. Existing private/no-store response headers remain.

My Activities keeps organized/joined/waitlisted relations and array pagination.
`joined` excludes CONFIRMATION_EXPIRED; `waitlisted` excludes WAITLIST_EXPIRED.
There is no new expired section. Existing upcoming/history end-time scopes and
activity ordering remain unchanged; filtering is based on persisted state until
the worker sweep. Organizer listings remain available independently of membership.

## Request-time correctness

Confirmation remains POST `/api/v1/activities/{id}/confirm`, no request body.
Only JOINED may confirm. It requires `opening <= now < effective_deadline`, with
UTC evaluated after the parent activity lock. Exact deadline returns 409
`Confirmation window has closed`, even if the worker has not changed the row yet.
`permissions.can_confirm` uses the same rule.

An overdue JOINED user also cannot leave and immediately rejoin to reset their
deadline. Such leave returns the same closed-window conflict and can_leave=false
until automation persists expiry. Before expiry, ordinary voluntary LEFT rejoin
remains eligible and obtains the deadline for its new place acquisition. Persisted
expired rows return 409 `Participation has expired` on attempted mutations.
Existing final-attendance conflicts remain unchanged.

CONFIRMED users can still leave until end unless cancelled. WAITLISTED users keep
their existing uncancelled before-end leave rule until a sweep expires the queue
at start; leaving the queue never grants a place or bypasses the start cutoff.
CHECKED_IN and final attendance remain non-leavable. GET endpoints do not reconcile
or mutate data; autonomous work does not require a user request.

## Sweep and transaction architecture

`run_participation_lifecycle_sweep(session_factory=None, now=None)` is a reusable
synchronous service. Explicit aware time supports deterministic tests. Production
captures candidate cutoff initially, then captures current UTC **again after
each parent lock**, including time spent waiting.

1. Select uncancelled activity IDs whose normal deadline could be due, using the
   existing start_at index and indexed correlated participation existence checks.
   Only JOINED, or WAITLISTED at/after start, makes an activity a candidate.
2. Close the candidate session. For each activity, create a fresh session and
   transaction, take the established parent-only SELECT FOR UPDATE, and refresh
   the activity through populate_existing. Deleted/cancelled activities are skipped.
3. Read that activity's JOINED user IDs/join timestamps in one projection. Evaluate
   the shared effective-deadline rule and expire all due rows in one bulk UPDATE.
4. Before start, if expiry released places, invoke the existing FIFO promotion
   service under the same lock. It counts actual free capacity and bulk-promotes
   earliest waiters, preserving `(waitlisted_at, user_id)` order. Three freed seats
   admit three earliest waiters when the queue has enough people. Promotion time
   becomes joined_at, naturally granting grace at/after normal deadline.
5. At/after start, never promote. Bulk-transition all remaining WAITLISTED to
   WAITLIST_EXPIRED. Commit that activity's expiry/promotion atomically.
6. Log and roll back a failed activity, continue unrelated candidates, and retry
   failed/unprocessed work on a later sweep. Aggregate statistics count only
   committed transitions. Repeated sweeps are idempotent.

Two application workers may choose the same candidate. They serialize on the
same activity lock; the second rereads current rows and cannot double-expire,
double-promote, or exceed capacity. Every ordinary join/rejoin/leave/confirm/
check-in/edit/cancel/finalize writer retains that activity-first protocol. No
participation-first lock, separate post-commit promotion, or SQLite-only shortcut
is used to establish concurrency correctness.

The candidate query avoids a full participation-table scan every interval. The
existing `(activity_id, status, waitlisted_at, user_id)` index supports state
existence, JOINED projection filtering, counts, and FIFO lookup; the activity
start_at index bounds candidate time. No additional index was justified. Grace
holders may be revisited until due, and old unresolved activities may be processed
after restart. Per-activity work grows with JOINED count, but there is no per-user
SELECT. One activity with expiry/promotion uses four SELECTs including candidate
selection and two bulk UPDATEs, regardless of tested membership count.

Discovery remains one SELECT; authenticated detail and My Activities remain two
including auth, independent of page size. Caller expiry fields are added to the
existing SQL projection, and effective timing is derived from already-returned
data. Existing query-count coverage remains in place.

## Lifespan worker, cancellation, and finalization

The FastAPI lifespan starts one named lifecycle task per enabled process. It runs
a sweep immediately, then waits the configured interval after each completed
sweep. It uses `asyncio.to_thread` for synchronous SQLAlchemy work, so the event
loop remains available. Each sweep/session belongs to its own thread; request
sessions are never shared. No BackgroundTasks, public scheduler endpoint, Celery,
Kafka, RabbitMQ, or WebSocket is introduced.

Shutdown sets a stop event, interrupts the interval wait, and awaits any in-flight
threaded sweep before finishing. Sessions close on all paths. Sweep exceptions
are logged and subsequent intervals continue; one activity failure also does not
prevent other activities from processing. Normal tests disable automatic startup;
dedicated tests cover enabled startup, off-loop execution, retry, and shutdown
while a synchronous sweep is still in flight, without real minute-long sleeps.

Cancellation wins serialization: cancelled activities are skipped without changing
JOINED/WAITLISTED/expired evidence. If a sweep commits first, later cancellation
preserves those transitions. Cancelled waitlists may therefore remain WAITLISTED
historically, matching existing cancellation policy. No new action becomes allowed.

Explicit organizer finalization remains unchanged and is never invoked by the
worker. It maps only the existing unresolved attendance states, never either
system-expired state. If automation was disabled/down and unresolved JOINED is
still stored when manual finalization wins the lock, the existing NO_SHOW mapping
still applies. There is no automatic finalization, reward, review, or XP handling.

## Migration and deployment limits

Upgrade adds two nullable timestamptz columns, widens status, and updates named
status/timestamp CHECKs. Existing rows/statuses/timestamps remain unchanged.
Downgrade preserves every row: CONFIRMATION_EXPIRED → LEFT with left_at equal to
confirmation_expired_at, losing automatic-vs-voluntary distinction;
WAITLIST_EXPIRED → WAITLISTED, preserving queue origin and null joined_at. It drops
0010 expiry timestamps and restores status length 16 / 0009 CHECKs. Re-upgrade
does not reconstruct expiry history. The complete 0009 → 0010 → 0009 → 0010 cycle
is tested in a generated temporary PostgreSQL/PostGIS database, never by
downgrading development data.

This worker runs only while an application process is alive. Sweep persistence
can lag a deadline by the interval, sweep duration, or lock contention; timestamps
record actual sweep time. A delayed sweep reaching start expires waiters rather
than promoting them. Multiple Uvicorn processes perform redundant attempts but
retain transactional correctness; there is no leader election or durable external
job queue. Graceful shutdown waits for current database work, including database
lock waits. These are deployment limits, not promises of exact wall-clock delivery.

## Frontend integration still required

The current frontend was inspected and left unchanged. `ActivityLifecycleInfo`
shows public dates, with no countdown or confirmation mutation. Participation is
still typed exactly null. My Activities remains mock-driven; detail query keys
lack identity, use 60-second staleTime, and have no periodic refetch interval.

- Add both expired states and nullable expiry/effective-deadline fields to the
  full participation object/null union, alongside the earlier WAITLISTED gap.
- Show a JOINED caller's countdown from effective_confirmation_deadline_at, while
  labeling top-level confirmation_deadline_at as the normal deadline. Respect
  server permissions and the exclusive deadline; hide confirm/check-in for expired
  or queued users and explain reservation/waitlist expiration in private detail.
- Replace My Activities mocks, keep the existing relations/scopes, and remove
  entries when server data no longer includes them. No expired section is required.
- Add polling/refetch for authenticated detail and personal lists during relevant
  pre-start windows, plus focus/reconnect refresh. No push channel exists. Observe
  promotion, another user's expiry, and queue disappearance after start through
  fresh server state; staleTime alone does not schedule refetch.
- Scope caches to identity, clear on account changes, and invalidate/refetch all
  affected activity/personal views after mutations and observed lifecycle changes.

The subsequent backend hardening milestone adds ENDED discovery filtering,
check-in accuracy_m, database readiness, auth refresh exception cleanup, and
production JWT-secret validation. These changes preserve the worker lifecycle
described here; see the [README](../../README.md) for the current API contracts.
