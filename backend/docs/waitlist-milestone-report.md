# Waitlist milestone report — 2026-10-19

Implemented on the current `backend` branch. Initial working tree was clean.
No commit, push, merge, or fetch was performed. Frontend files were inspected and
left unchanged. No scheduler or automatic confirmation expiry was implemented.

| # | Requested report item | Result |
| --- | --- | --- |
| 1 | Existing placeholders/frontend | Backend waitlist_count was hardcoded zero. Frontend already types/renders that count on limited detail, but participation is exactly null, Join has no handler, and My Activities uses static joined/organized IDs. No WAITLISTED source type or queue section existed. |
| 2 | WAITLISTED lifecycle | Requested place without active capacity; can leave, cannot confirm/check in; promotion grants JOINED only. |
| 3 | Database design | Existing composite PK and foreign keys retained; nullable waitlisted_at, nullable joined_at, strict per-state CHECKs, FIFO composite index. |
| 4 | waitlisted_at | Latest queue-entry time; required while queued, retained on promotion/departure, reset on a new cycle. |
| 5 | joined_at | Null while queued and after a never-joined queue departure; actual place-acquisition/promotion time otherwise. Required for all active/final attendance states. |
| 6 | FIFO ordering | waitlisted_at ASC then user_id ASC; one canonical key drives SQL position and promotion. |
| 7 | Migration | 20261018_0009_add_activity_waitlist.py, parent verified as 20261018_0008 in repository and development DB before implementation. |
| 8 | Upgrade | Existing rows/statuses/timestamps unchanged; waitlisted_at starts null. New state CHECKs retain existing attendance requirements. |
| 9 | Downgrade | WAITLISTED maps to inactive LEFT; never-joined rows use queue-entry time for legacy mandatory joined_at. Queue departure left_at is retained; queued left_at becomes downgrade time. Existing active/final data is unchanged. Queue history is lost; re-upgrade does not reconstruct it. This is a documented lossy legacy timestamp compromise. |
| 10 | Join with capacity | 201 ActivityRead, JOINED for unlimited or free limited capacity. |
| 11 | Join when full | 201 ActivityRead, WAITLISTED; full capacity alone no longer causes 409. |
| 12 | Join cutoff | UTC now < start_at only; exact start/later rejects join/rejoin/queue entry with 409. Ended/cancelled conflicts retain existing conventions. |
| 13 | Rejoin | Reuses LEFT row, resets cycle timestamps, chooses JOINED or WAITLISTED from actual capacity; final states remain terminal. |
| 14 | Leave waitlist | WAITLISTED → LEFT, retained row/queue time, no capacity release or promotion. Same uncancelled before-end leave eligibility as existing active departures. |
| 15 | Active leave/promotion | JOINED/CONFIRMED → LEFT, flush, actual capacity count, FIFO bulk promotion, response, commit in one transaction. After start, leave remains possible before end but promotion is closed. |
| 16 | Capacity increase | Before-start PATCH promotes into all actual free places; increasing by N admits up to N from a previously full queue. Limited → unlimited admits all. Reductions cannot evict active members. |
| 17 | participant_count | SQL count of JOINED/CONFIRMED/CHECKED_IN only. |
| 18 | waitlist_count | Real SQL count of WAITLISTED only, including retained historical queues in direct detail/personal views. |
| 19 | waitlist_position | Caller-only SQL count of queued keys <= caller key, 1-based; null outside WAITLISTED. No Python queue loading. |
| 20 | My Activities relation | relation=waitlisted selects caller WAITLISTED only; joined excludes it. Existing array/pagination/order retained; upcoming remains end_at > cutoff, history <= cutoff for every relation. |
| 21 | Caller participation | WAITLISTED exposes queue-entry time/position with null join/attendance times; promoted JOINED retains queue context and null position. LEFT/anonymous/unrelated stay null. |
| 22 | Permissions | Full activities remain joinable before start. Queued users may leave before end unless cancelled, with join/confirm/check-in false. All participant actions false for ended/cancelled activity. can_join permits either JOINED or WAITLISTED, without promising a place. |
| 23 | Confirm/check-in | Queued requests return existing 409 Not participating in this activity. Promotion does not confirm automatically. Existing windows/proximity behavior unchanged. |
| 24 | Cancellation | Rows/timestamps preserved, discovery excluded, direct detail/personal relations retained, all mutations/promotions blocked after cancellation wins serialization. |
| 25 | Finalization | WAITLISTED is never COMPLETED/NO_SHOW and remains historically queued; a waitlist-only ended activity has no attendance to finalize. |
| 26 | Locking | Existing activity-first SELECT FOR UPDATE, READ COMMITTED, populate_existing refresh after waiting; helper does not independently lock participation or commit. |
| 27 | Concurrency | Nine new scenarios in both observed lock orders: last slot, full multi-join, leave/promotion, two leaves, queue departures, rejoin race, capacity increase, cancel/leave, cancel/capacity. Existing PostgreSQL race coverage retained. |
| 28 | FIFO determinism | Controlled distinct, equal, and microsecond timestamps; UUID tie-breaker; position matches actual promotion order. No sleep-based timestamp ordering. |
| 29 | Queries/N+1 | Public discovery 1 SELECT; authenticated detail/My Activities 2 including auth, at one/many activities. SQL counts/rank, eager organizer, no per-activity round trips. PostgreSQL EXPLAIN on 6,000 waiters uses FIFO index without Sort. |
| 30 | Files created | Seven, listed below: migration, helper, three test modules, waitlist contract, this report. |
| 31 | Files modified | 23 tracked existing files, listed in the final status below. |
| 32 | Documentation | README; participation, My Activities, management, check-in, finalization; new waitlist contract; Swagger response fields/examples, join/leave/management/finalization docs, relation enum. |
| 33 | Tests added | 80 collected cases: 56 isolated and 24 PostgreSQL, including migration cycle and query-plan validation. Existing full-conflict and after-start join expectations updated as explicitly required. |
| 34 | Default pytest | uv run pytest -v: 460 passed, 122 skipped, 1 existing warning; 32.28 seconds. Baseline before implementation: 404 passed, 98 skipped. |
| 35 | PostgreSQL/PostGIS | Separate complete twelve-module run: 122 passed, 18 existing warnings; 29.58 seconds. Baseline: 98 passed. Runs used a separate task-created database. |
| 36 | Migration cycle | 0008 → 0009 → 0008 → 0009 passed in a generated temporary PostGIS database, with all existing statuses, queue rows, departed queue rows, promoted rows, preservation and invalid-state checks. Prior migration cycles also passed. |
| 37 | Ruff | uv run ruff check . passed. |
| 38 | compileall | uv run python -m compileall app passed. |
| 39 | uv lock | uv lock --check passed; lockfile unchanged. A workspace-local uv cache was used because the default cache was inaccessible. |
| 40 | Alembic current | Repository and development database now 20261018_0009 (head). Development counts preserved: 2 users, 1 activity, 0 participations; existing participation digest unchanged. Only a forward development migration was run. |
| 41 | Diff whitespace | git diff --check passed. |
| 42 | Working tree | Final git status --short recorded below. Only intended backend/README changes, no commit. |
| 43 | Frontend unchanged | git diff -- frontend empty; no frontend file was written. |
| 44 | Remaining frontend work | Exact integration list below and in activity-waitlist.md. |
| 45 | Limitations | No scheduler, expiry, timeout promotion, push notifications, or immutable cycle audit. Historical waitlists remain; positions are snapshots. Cooperating service writers enforce capacity; arbitrary SQL can bypass the parent-lock protocol. Downgrade loses queue semantics/history. |
| 46 | Recommended next milestone | Define stale-queue and confirmation-deadline policies, then implement scheduler/expiry and timeout-driven promotion using the same parent lock. Keep frontend integration as a separate change. |

## Created files

- backend/alembic/versions/20261018_0009_add_activity_waitlist.py
- backend/app/services/waitlist_service.py
- backend/tests/test_waitlist.py
- backend/tests/test_waitlist_postgres.py
- backend/tests/test_waitlist_migration_postgres.py
- backend/docs/activity-waitlist.md
- backend/docs/waitlist-milestone-report.md

## Exact frontend follow-up

1. `src/types/activity.ts`: replace the exactly-null participation field with the
   WAITLISTED/JOINED/CONFIRMED/CHECKED_IN/COMPLETED/NO_SHOW object/null union. Add
   nullable joined_at, waitlisted_at, waitlist_position and attendance timestamps;
   include existing backend can_cancel/can_finalize/cancelled_at gaps.
2. `src/api/activitiesApi.ts` and mutation hooks: add POST join and DELETE join
   (also used for queue departure), pending/error handling, and status-dependent
   success feedback. A 201 may mean JOINED or WAITLISTED.
3. Activity detail: retain Join on full activity whenever can_join=true; show
   queued state/position and Leave waitlist. Stop admission at start using server
   permissions. Hide confirm/check-in controls while queued; use normal JOINED
   controls after a refreshed response shows promotion.
4. Reuse the existing waitlist_count number/rendering as live persisted data.
   Queue position is private and separate from that public count.
5. My Activities: replace mocks with authenticated array queries for upcoming
   joined, upcoming waitlisted, all organized, and joined history. Add a Waitlist
   section, pagination, queue position, cancelled/ended context, and loading/errors.
   Keep server end-time scope semantics. Historical waitlisted lists are available
   through relation=waitlisted&scope=history if the UI needs them.
6. Query keys: include user identity for personal/detail state, clear on account
   changes, and invalidate discovery/detail/joined/waitlisted/organized views after
   mutations. Refetch on focus or explicit refresh to observe promotions caused by
   other users/capacity edits; there is no server push channel in this milestone.
7. Update mocks to realistic status/time/count examples when frontend work starts.
   Existing confirmation, check-in/geolocation, and organizer action integration
   remain separate frontend gaps.

## Final git status --short

```text
 M README.md
 M backend/app/api/v1/activities.py
 M backend/app/api/v1/users.py
 M backend/app/models/activity_participation.py
 M backend/app/schemas/activity.py
 M backend/app/schemas/my_activities.py
 M backend/app/services/activity_management_service.py
 M backend/app/services/activity_service.py
 M backend/app/services/participation_rules.py
 M backend/app/services/participation_service.py
 M backend/docs/activity-check-in.md
 M backend/docs/activity-finalization.md
 M backend/docs/activity-management.md
 M backend/docs/activity-participation.md
 M backend/docs/my-activities.md
 M backend/tests/test_activity_finalization_postgres.py
 M backend/tests/test_activity_management_postgres.py
 M backend/tests/test_my_activities.py
 M backend/tests/test_openapi.py
 M backend/tests/test_participation.py
 M backend/tests/test_participation_lifecycle.py
 M backend/tests/test_participation_lifecycle_postgres.py
 M backend/tests/test_participation_postgres.py
?? backend/alembic/versions/20261018_0009_add_activity_waitlist.py
?? backend/app/services/waitlist_service.py
?? backend/docs/activity-waitlist.md
?? backend/docs/waitlist-milestone-report.md
?? backend/tests/test_waitlist.py
?? backend/tests/test_waitlist_migration_postgres.py
?? backend/tests/test_waitlist_postgres.py
```

Existing warnings: Starlette TestClient/httpx deprecation, Alembic path_separator
deprecation, and local pytest-cache permissions in the PostgreSQL run. Git may
also report the existing unreadable root .pytest_cache and LF/CRLF notices. None
was suppressed. The task-created test database was dropped; development data and
its persistent Docker volume were preserved.
