# Automated lifecycle milestone report — 2026-10-19

Work stayed on `backend`, starting from a clean working tree. Repository and
development DB were verified at `20261018_0009` before implementation. Baselines
were rerun: 460 default tests passed / 122 skipped, and 122 separate PostgreSQL
tests passed. No commit, push, merge, rebase, or fetch was performed.

| # | Requested report item | Result |
| --- | --- | --- |
| 1 | Existing architecture | Synchronous SQLAlchemy, READ COMMITTED, activity-first locks; old confirmation opened 24 hours before start and closed at start. No lifespan worker existed. Frontend shows public timing only, has no countdown/actions, types participation as null, and uses My Activities mocks. |
| 2 | New window | Opening defaults to start minus 60 minutes; normal deadline start minus 30 minutes. Opening inclusive, deadline exclusive. |
| 3 | Configuration | Added ACTIVITY_CONFIRMATION_OPEN_MINUTES_BEFORE=60, ACTIVITY_CONFIRMATION_DEADLINE_MINUTES_BEFORE=30, ACTIVITY_LATE_CONFIRMATION_GRACE_MINUTES=10, PARTICIPATION_LIFECYCLE_WORKER_ENABLED=true, PARTICIPATION_LIFECYCLE_SWEEP_INTERVAL_SECONDS=60. Validated offsets/grace/finite positive interval. Removed old hours setting; private .env unchanged. |
| 4 | CONFIRMATION_EXPIRED | System-released unconfirmed JOINED place; inactive and terminal. Never voluntary LEFT and never rejoinable. |
| 5 | WAITLIST_EXPIRED | Never-admitted waiter when start is reached; inactive, terminal, never NO_SHOW. |
| 6 | Migration | 20261019_0010_add_participation_expiry.py, parent 20261018_0009. Status widens to VARCHAR(24), adds two nullable timestamptz columns and strict named CHECKs. No new indexes or event log. |
| 7 | Upgrade | Existing rows/statuses/timestamps/defaults/keys/indexes preserved; new expiry fields null. |
| 8 | Downgrade | Preserves every row: CONFIRMATION_EXPIRED → LEFT with left_at from expiry time; WAITLIST_EXPIRED → WAITLISTED retaining queue origin/null joined_at. Drops new timestamps and restores width/checks. Loses system-versus-voluntary distinction and expiry history. |
| 9 | confirmation_expired_at | Actual UTC sweep time, only for CONFIRMATION_EXPIRED; original joined_at and any queue origin preserved. |
| 10 | waitlist_expired_at | Actual UTC sweep time at/after start, only for WAITLIST_EXPIRED; joined_at remains null. |
| 11 | Normal deadline | start_at minus configurable deadline offset; public confirmation_deadline_at is independent of authentication. |
| 12 | Grace | Applies to direct joins, promotions, and eligible LEFT rejoins whose new joined_at is at/after normal deadline; default 10 minutes, capped at start. |
| 13 | Effective calculation | Central helper: joined_at < normal deadline uses normal deadline; otherwise min(joined_at + grace, start_at). Derived, not persisted. Exposed only for caller JOINED, null for other states. |
| 14 | Exact boundaries | At opening allowed; at normal/effective deadline rejected. Promotion exactly at normal deadline gets grace; just before it retains the remaining normal window. No admission/promotion at start. |
| 15 | Automatic expiry | Per-activity locked transaction projects JOINED timestamps once, bulk-expires due rows, then releases/promotes before commit. No HTTP request is needed. |
| 16 | FIFO promotion | Reuses unchanged existing promotion helper and canonical waitlisted_at ASC/user_id ASC key, retaining queue timestamp and setting joined_at to sweep time. |
| 17 | Multi-seat behavior | All due places are released together and earliest waiting users fill actual capacity in one promotion UPDATE; repeated grace-expiry rounds are supported. |
| 18 | Queue at start | Bulk WAITLISTED → WAITLIST_EXPIRED, zero promotions once start is reached. Counts/personal membership filters stop including persisted expired rows. |
| 19 | participant_count | Still JOINED + CONFIRMED + CHECKED_IN only. Overdue-but-unswept JOINED remains counted until persistence; permissions already reject overdue confirmation/leave. |
| 20 | waitlist_count | WAITLISTED only; neither expired state counts. Cancellation preserves original evidence and is skipped. |
| 21 | Caller participation | Direct detail privately exposes either expired state and its timestamp, with all participant actions false. JOINED exposes effective deadline. Anonymous/unrelated callers receive no other person's state; LEFT remains null. |
| 22 | My Activities | Existing organized/joined/waitlisted relations, arrays, scopes, sorting and pagination retained. Joined excludes confirmation expiry; waitlisted excludes waitlist expiry. No expired section added. |
| 23 | Permissions | can_confirm uses effective deadline even before worker processing. Overdue JOINED can_leave=false prevents leave/rejoin deadline bypass. Persisted expired states permit no participant actions. |
| 24 | Join/rejoin | Still strictly before start. Full capacity still returns WAITLISTED/201; free/unlimited returns JOINED/201. LEFT reuses row and gets new-cycle deadline. Expired states cannot reset into a new cycle. |
| 25 | Cancellation | Skip cancelled candidates and recheck after the lock. Cancellation winning serialization prevents expiry/promotion; cancellation after a sweep preserves its committed evidence. |
| 26 | Finalization | No automatic finalization. Existing explicit organizer mapping is unchanged and excludes both expired states. When automation is disabled/down, manual finalization can still resolve stored unresolved JOINED to NO_SHOW under existing rules. |
| 27 | Sweep architecture | Reusable run_participation_lifecycle_sweep(factory, now=...) with aware deterministic test time; separate candidate session and per-activity transaction/session. Failed activities roll back, log, and do not prevent unrelated work. |
| 28 | FastAPI worker | Lifespan creates one named task per enabled process, immediate sweep then periodic interval waits. No BackgroundTasks or public scheduler endpoint. |
| 29 | Startup/shutdown | Start once per process, cooperative stop event interrupts interval waits, await in-flight synchronous work before exit. Exceptions logged; later sweeps continue. |
| 30 | Sync/async safety | asyncio.to_thread performs synchronous DB work off the event loop. Each sweep owns its sessions; no request Session is shared across tasks/threads. |
| 31 | Multi-worker safety | Redundant candidate selection is acceptable; PostgreSQL locks plus refreshed state make overlapping sweeps idempotent and prevent duplicate promotions/overbooking. No leader election/external job queue. |
| 32 | Locking | Existing parent-only SELECT FOR UPDATE under READ COMMITTED retained. Production time is captured again after waiting for each lock; no participation-first lock path. |
| 33 | Concurrency tests | Eleven scenarios in both real observed lock orders: confirm before/at deadline, leave before/at deadline, cancellation, FIFO expiry promotion, multiple expiries, grace expiry, waiter leave, start expiry, and multiple sweeps. Additional test advances the clock across start while the worker waits on the activity lock. |
| 34 | Time tests | Exact opening/normal/grace deadlines, early/equal/late joined_at, microsecond-before boundaries, start cap, late direct join/rejoin, repeated promotion rounds, and post-lock clock refresh; no real minute-long sleeps. |
| 35 | No-request test | Seeds through DB/service calls, directly runs the sweep without TestClient/HTTP, verifies expiry/promotion/repeated rounds/idempotency. Worker lifespan tests independently establish autonomous startup. |
| 36 | Performance | Existing start_at and activity/status/FIFO indexes support candidate filtering and state lookup; no full participation-table scan per interval or per-user SELECT loops. Four SELECTs/two bulk UPDATEs for tested single-activity expiry/promotion at different membership counts. Read-route round-trip guarantees unchanged. |
| 37 | Files created | Nine files: migration, lifecycle service, two worker package files, three test modules, worker contract, this report. Exact paths below. |
| 38 | Files modified | 32 existing tracked files: settings/example env, app/schema/services, tests, README and six contracts. Exact status below. |
| 39 | Documentation | README, participation/waitlist/My Activities/management/check-in/finalization contracts, new worker contract; OpenAPI normal/effective deadline, expiry states/errors/examples, and no scheduler API. |
| 40 | Tests added | 82 cases: 58 default + 24 PostgreSQL. Existing regression fixtures explicitly configure broader windows where their original scenarios require them; dedicated tests verify the new defaults. |
| 41 | Default pytest | uv run pytest -v: 518 passed, 146 skipped, one existing warning; 38.75 seconds. |
| 42 | PostgreSQL/PostGIS | Separate full fourteen-module run: 146 passed, 22 existing warnings; 38.93 seconds. Uses task-created database, removed afterward. |
| 43 | Migration cycle | 0009 → 0010 → 0009 → 0010 passed in generated temporary PostgreSQL/PostGIS, including every previous status, promoted queue context, never-joined LEFT, integrity rejection, and row-preserving downgrade mappings. Prior cycles also passed. |
| 44 | Ruff | uv run ruff check . passed. |
| 45 | compileall | uv run python -m compileall app passed. |
| 46 | uv lock | uv lock --check passed; lockfile unchanged. Workspace-local cache used because default user cache was inaccessible. |
| 47 | Alembic current | Repository/development DB now 20261019_0010 (head). Only forward migration applied to development. Counts unchanged: 2 users, 1 activity, 0 participations; hashes of all existing table data matched before/after. |
| 48 | Whitespace | git diff --check passed. |
| 49 | Working tree | Intended backend/README changes only; exact git status --short below. No commit. |
| 50 | Frontend unchanged | git diff -- frontend empty; no frontend file written. |
| 51 | Frontend follow-up | Full participation union/new expired states, effective countdown, expiry messaging, real personal lists, promotion/start-expiry refresh, identity-scoped caches, periodic/focus/reconnect refetch. Details below. |
| 52 | Worker/deployment limits | Requires a running app process; persistence may lag interval + sweep duration/locks. Counts reflect persisted state. Multiple processes do redundant work. Shutdown waits for in-flight DB work. No durable scheduler, leader election, notifications, push, or auto finalization. |
| 53 | Recommended hardening | Separate final backend hardening milestone: ENDED discovery filtering, check-in accuracy_m, readiness endpoint, auth refresh exception cleanup, production JWT-secret validation. None implemented here. |

## Created files

- backend/alembic/versions/20261019_0010_add_participation_expiry.py
- backend/app/services/participation_lifecycle_service.py
- backend/app/workers/__init__.py
- backend/app/workers/participation_lifecycle.py
- backend/tests/test_lifecycle_worker.py
- backend/tests/test_lifecycle_worker_postgres.py
- backend/tests/test_lifecycle_worker_migration_postgres.py
- backend/docs/participation-lifecycle-worker.md
- backend/docs/participation-lifecycle-milestone-report.md

## Exact frontend integration work

1. `src/types/activity.ts`: replace exactly-null participation with the full
   object/null union, adding CONFIRMATION_EXPIRED and WAITLIST_EXPIRED along with
   the existing unintegrated WAITLISTED/current/final states. Include nullable
   joined_at, waitlisted_at, waitlist_position, effective_confirmation_deadline_at,
   confirmation_expired_at, waitlist_expired_at and attendance timestamps. Existing
   can_cancel/can_finalize/cancelled_at gaps remain.
2. `ActivityLifecycleInfo`: distinguish the public normal deadline from the
   JOINED caller's effective deadline. Build any countdown from the effective
   deadline; staleTime is not a timer. Respect inclusive opening/exclusive deadline
   and can_confirm; normal timing may have closed while grace remains available.
3. Detail actions: wire join/leave/confirm/check-in and status-dependent feedback.
   Display terminal reservation/waitlist expiry explanations from private detail;
   hide participation controls for expired/queued states as appropriate. An overdue
   JOINED may already have can_confirm/can_leave=false before the sweep persists
   the final expired state; refresh rather than offering deadline-reset rejoin.
4. My Activities: replace joined/organized mock IDs with authenticated existing
   relations/scopes and add Waitlist integration. Remove entries on refreshed data
   after promotion/expiry; no new expired section is required. Expired explanation
   remains available through direct activity detail.
5. Queries/cache: identity-scope detail and personal keys; remove on account changes;
   invalidate/refetch affected views after mutations. Add bounded periodic refetch
   during relevant pre-start windows, plus focus/reconnect refresh, to observe
   another user's expiry, promotion, or queue expiry at start. The existing detail
   query has 60-second staleTime but no refetchInterval and no user identity key.
   No WebSockets or notification channel was added.
6. Update mocks when frontend integration begins. Existing API/mutation, loading,
   pagination, geolocation and organizer-management integration remain frontend
   work. Frontend source stayed unchanged in this milestone.

## Final git status --short

```text
 M README.md
 M backend/.env.example
 M backend/app/api/v1/activities.py
 M backend/app/api/v1/users.py
 M backend/app/core/config.py
 M backend/app/main.py
 M backend/app/models/activity_participation.py
 M backend/app/schemas/activity.py
 M backend/app/schemas/my_activities.py
 M backend/app/services/activity_service.py
 M backend/app/services/participation_rules.py
 M backend/app/services/participation_service.py
 M backend/docs/activity-check-in.md
 M backend/docs/activity-finalization.md
 M backend/docs/activity-management.md
 M backend/docs/activity-participation.md
 M backend/docs/activity-waitlist.md
 M backend/docs/my-activities.md
 M backend/tests/conftest.py
 M backend/tests/test_activities.py
 M backend/tests/test_activity_finalization_postgres.py
 M backend/tests/test_activity_management.py
 M backend/tests/test_check_in.py
 M backend/tests/test_check_in_postgres.py
 M backend/tests/test_my_activities.py
 M backend/tests/test_my_activities_postgres.py
 M backend/tests/test_openapi.py
 M backend/tests/test_participation.py
 M backend/tests/test_participation_lifecycle.py
 M backend/tests/test_participation_lifecycle_postgres.py
 M backend/tests/test_participation_postgres.py
 M backend/tests/test_waitlist.py
?? backend/alembic/versions/20261019_0010_add_participation_expiry.py
?? backend/app/services/participation_lifecycle_service.py
?? backend/app/workers/
?? backend/docs/participation-lifecycle-milestone-report.md
?? backend/docs/participation-lifecycle-worker.md
?? backend/tests/test_lifecycle_worker.py
?? backend/tests/test_lifecycle_worker_migration_postgres.py
?? backend/tests/test_lifecycle_worker_postgres.py
```

The existing Starlette TestClient/httpx warning, Alembic path_separator deprecation,
and PostgreSQL-run pytest-cache permission warning were retained. Git may report
the existing unreadable root .pytest_cache and LF/CRLF notices. The isolated test
database was removed; development data and its persistent Docker volume were
preserved. A focused 15-test OpenAPI run also passed after final example updates.
