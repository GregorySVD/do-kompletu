# Organizer participation integration correction

Verified 2026-11-08, starting from clean branch `backend`, HEAD `c661111`.
Scope is the organizer participation correction during backend feature freeze.
No Git write operations, commit, push, PR, frontend change, dependency change,
new endpoint, new participation status, or organizer-specific reward was made.

## Requested review points

| # | Item | Result |
| --- | --- | --- |
| 1 | Branch and HEAD | `backend`, `c661111`; unchanged. Initial working tree clean. |
| 2 | Actual baseline | Default `uv run pytest -v`: **760 passed, 177 skipped**, 44.51s. Separate real PostgreSQL/PostGIS suite: **176 passed**, 42.45s. Ruff, compileall, and `uv lock --check` passed. Repository head was `20261031_0012`; actual development database was `20261030_0011`. |
| 3 | Old behavior discovered | Creation committed Activity alone. Shared participation lock validation rejected organizer check-in. Permission generation excluded organizers from check-in, and joined My Activities explicitly excluded their activities. Counts and gallery uploads therefore had no organizer participation to use. |
| 4 | New semantics | Every activity created through the service/API, or newly inserted by the SQL seed script, gets a real organizer participation in CONFIRMED. It persists through the ordinary lifecycle. Active eligible legacy activities receive the same state through the data migration. |
| 5 | Creation transaction | Add Activity, flush ID, add organizer participation, flush, read the full response snapshot, commit once. Any insert, snapshot, or commit failure rolls back. Seed creation uses one data-modifying CTE statement for both inserts. |
| 6 | Initial state and timestamps | CONFIRMED; `joined_at == confirmed_at` is the UTC automatic commitment time. Both are required by the current CONFIRMED check constraint. Creation captures one application UTC timestamp after Activity flush; backfill uses PostgreSQL transaction_timestamp(). Check-in, completion, no-show, leave, queue and expiry timestamps remain null. |
| 7 | Duplicate protection | Existing composite primary key `(activity_id, user_id)` is reused. No redundant schema constraint. Backfill uses missing-row selection and `ON CONFLICT DO NOTHING`; existing rows of every state and their timestamps are unchanged. |
| 8 | participant_count | Unchanged database projection of JOINED + CONFIRMED + CHECKED_IN naturally includes organizer. New activity starts at 1; final COMPLETED/NO_SHOW rows do not consume active capacity. No organizer +1 arithmetic. |
| 9 | available_slots | Finite maximum minus actual active count, floored at zero; unlimited remains null. A new max=10 activity returns 9. The floor safely handles full legacy activities receiving one extra organizer without concealing the true count. |
| 10 | Minimum/maximum | Organizer counts toward both through the real active row. Existing API/database product rules remain min 2..100, finite max 2..100 and max >= min. Thus max=1 remains 422; it was not permitted before this task. Lowest valid max=2 leaves one external place. |
| 11 | Waitlist | With max=2, organizer CONFIRMED + external A JOINED fills capacity; B WAITLISTED. Ordinary leave promotes FIFO under the same parent lock. Organizer never joins the queue or frees a place through leave. Legacy overcapacity preserves everyone and delays promotion until a real place opens. |
| 12 | Organizer JOIN | Explicitly rejected with 409 by operation-specific non-organizer validation. No duplicate participation. |
| 13 | Organizer LEAVE | Explicitly rejected with 409, including CHECKED_IN/final lifecycle evidence. Automatic participation is not deleted. |
| 14 | Organizer CONFIRM/rejoin | Normal confirmation remains explicitly rejected with 409. Organizer cannot use LEFT -> JOINED rejoin, including a deliberately inconsistent legacy LEFT fixture. |
| 15 | Organizer CHECK-IN | Uses existing POST `/api/v1/activities/{activity_id}/check-in`. Requires normal active authentication, CONFIRMED participation, open lifecycle/window, valid latitude/longitude/required accuracy, configured accuracy limit and real PostGIS radius. No role bypass or approximate location fallback. Duplicate/cancelled/ended attempts remain rejected. |
| 16 | can_check_in | Same state/time eligibility for every authenticated CONFIRMED participant: false before opening, true inside the window, false after check-in. POST still independently validates accuracy and distance. |
| 17 | current_user_participation | Existing caller-private DTO now exposes organizer CONFIRMED -> CHECKED_IN -> COMPLETED, or normal NO_SHOW if never checked in. Historical legacy rows intentionally absent remain null. No special organizer schema. |
| 18 | checked_in_count | Existing CHECKED_IN + COMPLETED database projection includes organizer; successful organizer-only check-in gives 1, retained after completion. |
| 19 | Gallery viewing | Existing organizer viewing remains available strictly before end_at + 72h, including cancellation. Existing attendance-based access for other participants is unchanged. |
| 20 | Gallery upload | Organizer CONFIRMED cannot upload. CHECKED_IN/COMPLETED enables the same upload path, subject to cancellation, strict 72h closure, max 3, image MIME/content/size validation, storage compensation and existing locks. Identity alone grants no upload. |
| 21 | Cancellation | Ordinary organizer and existing admin cancellation paths remain unchanged. Participation/photos/timestamps remain evidence; no new check-in/upload or finalization; historical gallery viewing follows existing rules. Admins are not made participants unless they organize the activity. |
| 22 | Finalization | Existing bulk transitions apply without organizer exceptions: CHECKED_IN -> COMPLETED, JOINED/CONFIRMED -> NO_SHOW. Parent-first lock, snapshot-before-commit, final timestamps and retry 409 remain. No automatic finalization. |
| 23 | Points | Exactly the existing +10 for a newly changed CHECKED_IN -> COMPLETED row, including organizer. Creating/organizing/finalizing without attendance earns zero. Attendance and arithmetic points update commit together; retries and concurrent finalizers do not double-award. |
| 24 | Lifecycle worker | Unchanged candidate/reconciliation queries expire only JOINED and remaining WAITLISTED. Organizer starts CONFIRMED and is not confirmation-expired. Normal expiry, grace deadlines and FIFO promotion are preserved. |
| 25 | My Activities | organized remains ownership-based. joined now includes any real eligible organizer participation; EXISTS prevents duplicates inside a relation/page. The same activity can appear once in each separately requested organized/joined relation. Historical organizer events without participation remain organized only; waitlisted still excludes organizer-owned events. |
| 26 | Migration | New linear data-only `20261108_0013_organizer_participation.py`, parent `20261031_0012`. Existing revisions, schema and statuses unchanged. |
| 27 | Active backfill | Eligibility is noncancelled, missing organizer row, `end_at > TIMESTAMPTZ '2026-11-08 00:00:00+00'`. Ordered activity-first FOR UPDATE CTE precedes child insertion. Actual insertion transaction time populates placement/automatic confirmation. Existing participants/limits/queues are not rewritten or demoted. |
| 28 | Ended historical strategy | End at/before the fixed cutoff is skipped; no synthetic CONFIRMED, CHECKED_IN, COMPLETED or NO_SHOW. Existing attendance is untouched. An event active at the fixed cutoff can qualify even if ended by a delayed deployment; classification deliberately does not drift with execution time. |
| 29 | Cancelled historical strategy | Already-cancelled activities missing organizer participation are skipped. Cancellation and any existing attendance/photo evidence are preserved. |
| 30 | Migration idempotency | Fixed classification cutoff, missing-row predicate and existing PK conflict handling make direct replay/re-upgrade duplicate-safe; existing evidence and automatic confirmation timestamps are not rewritten. |
| 31 | Downgrade safety | Intentionally no-op for data. Without provenance metadata even an unchanged CONFIRMED row cannot be safely distinguished from genuine commitment. All participation, later check-ins/completion, photos and points remain. No provenance column or destructive deletion added. |
| 32 | Files created | New migration, three organizer acceptance/migration test modules, and this report. Exact inventory below. |
| 33 | Files modified | Services, API/schema descriptions/examples, SQL seed, relevant existing regression tests, README and current domain contracts. Exact inventory below. |
| 34 | Existing tests updated | Organizer-absence assertions and capacities corrected according to domain meaning. Fixtures needing the same number of external participants receive one additional total place. Direct ORM legacy fixtures remain legacy. New organizer NO_SHOW/current-state/count expectations replace old owner-only expectations. |
| 35 | New acceptance tests | **32 default organizer cases** plus **12 real PostgreSQL cases** and **4 dedicated PostgreSQL migration cases**. Tests cover creation/real constraint-failure rollback, duplicate PK, operations/rejoin guards, min=2 preservation, permissions, check-in, galleries, lifecycle, FIFO, My Activities, schedule protection, completion/no-show/points, seed atomicity and legacy overflow. |
| 36 | PostgreSQL tests | Separate full suite uses task-created `dk_organizer_test_20261108`, READ COMMITTED and actual PostGIS. Migration-cycle fixtures create/drop their own generated databases. SQLite/mocks are not presented as proof of locking or spatial validation. |
| 37 | Concurrency regressions | Existing parent-lock race suites preserved. New tests observe organizer check-in and concurrent finalizers waiting for the activity lock, then verify one transition/one reward. New creation test proves another connection cannot see the flushed Activity before participation commit. |
| 38 | Gallery regressions | Full existing default and PostgreSQL gallery suites plus new organizer before/after check-in uploads, max-three, exact 72h closure and cancellation evidence tests. Existing storage compensation tests run; optional live S3 integration remains unconfigured/skipped. |
| 39 | Points/finalization regressions | Full existing default and real PostgreSQL points/finalization suites plus organizer +10 completion, zero organizing-only/NO_SHOW award, retry and concurrent exactly-once cases. |
| 40 | Final default pytest | `uv run pytest -v`: **791 passed, 193 skipped**, 46.31s. The 192 PostgreSQL cases run separately below; one optional live S3 integration remains unconfigured. |
| 41 | Final PostgreSQL/PostGIS | Separate full `uv run pytest -v @organizerPgFiles`: **192 passed**, 47.62s. Includes all PostgreSQL modules, actual PostGIS, all existing migration cycles, four new backfill cases, gallery, admin cancellation and concurrent points/finalization regressions. |
| 42 | Ruff | `uv run ruff check .`: passed, All checks passed. |
| 43 | compileall | `uv run python -m compileall app`: passed. |
| 44 | uv lock | `uv lock --check`: passed, 72 packages; dependency/lockfile unchanged. |
| 45 | Alembic current | Development remains `20261030_0011` as found; deliberately not migrated. Repository head is `20261108_0013`; isolated test database upgraded to `20261108_0013 (head)`. Apply the pending existing admin revision and new data revision through the normal deployment process. |
| 46 | Migration cycle | Four dedicated real PostgreSQL tests passed, including 0012 -> 0013 -> 0012 -> 0013 and direct backfill replay with evidence/points preservation. All preexisting migration-cycle tests are included in the full PostgreSQL run. |
| 47 | git diff --check | Passed; no whitespace errors. Git's preexisting LF/CRLF conversion notices are warnings, not errors. |
| 48 | Git status | 34 modified tracked files and 5 new files, all listed below; uncommitted on backend. No Git write operation. |
| 49 | Frontend unchanged | No frontend writes; `git diff -- frontend` is empty. |
| 50 | Observable frontend effect | Create now returns organizer `current_user_participation.status=CONFIRMED`, nonnull equal joined_at/confirmed_at, participant_count=1 and finite available_slots=max-1. During check-in window can_check_in becomes true; success yields CHECKED_IN, checked_in_count includes organizer, upload becomes eligible. Finalization yields COMPLETED/+10 or normal NO_SHOW. Organizer join/leave/confirm stay false. organized and joined can both contain the same real participation, once per response. JSON shapes and endpoints unchanged. |
| 51 | Known limitations | Development migration pending; historical/cancelled legacy activities may intentionally lack organizer participation; existing unusual organizer rows are preserved rather than normalized. A full legacy event can temporarily exceed max by one after backfill. Fixed cutoff classification applies at the documented instant, not deployment time. Existing self-reported GPS/spoofing, manual finalization and optional live-storage limitations remain. Conservative downgrade retains data. |
| 52 | Ready for commit/review | **Yes**, for this integration correction. Required test/static checks and independent production/coverage reviews passed. Development database upgrade remains a deployment step, explicitly unperformed. No commit or push performed. Work stops after this correction. |

## Compatibility details

Automatic CONFIRMED organizer commitment alone is excluded only from the internal
schedule-protection count: otherwise newly created events would become immediately
uneditable in time. Other participants' CONFIRMED state still protects the
schedule, and any CHECKED_IN/COMPLETED participant, including organizer, retains
schedule protection. Any successful check-in still protects venue coordinates,
name and address. Capacity, attendance counts and finalization include organizer
without this exception. Ownership/admin authorization is unchanged.

The invariant applies to service/API-created activities, newly inserted SQL seed
activities, and eligible legacy activities missing an organizer row at backfill.
Raw SQL or direct ORM insertion outside these creation paths is not protected by
a new database trigger. Historical/cancelled seed rows skipped by ON CONFLICT are
not retroactively changed by the seed; the migration is the legacy adoption path.

## Exact file inventory

Created:

- `backend/alembic/versions/20261108_0013_organizer_participation.py`
- `backend/tests/test_organizer_participation.py`
- `backend/tests/test_organizer_participation_postgres.py`
- `backend/tests/test_organizer_participation_migration_postgres.py`
- `backend/docs/organizer-participation-report.md`

Modified production/seed files:

- `backend/app/services/activity_service.py`
- `backend/app/services/participation_service.py`
- `backend/app/api/v1/activities.py`
- `backend/app/api/v1/users.py`
- `backend/app/schemas/activity.py`
- `backend/app/schemas/activity_management.py`
- `backend/app/schemas/my_activities.py`
- `backend/do_kompletu_seed_activities.sql`

Modified existing tests:

- `backend/tests/test_activities.py`
- `backend/tests/test_activity_finalization.py`
- `backend/tests/test_activity_finalization_postgres.py`
- `backend/tests/test_activity_management.py`
- `backend/tests/test_activity_management_postgres.py`
- `backend/tests/test_admin_postgres.py`
- `backend/tests/test_check_in.py`
- `backend/tests/test_check_in_postgres.py`
- `backend/tests/test_lifecycle_worker.py`
- `backend/tests/test_lifecycle_worker_postgres.py`
- `backend/tests/test_openapi.py`
- `backend/tests/test_participation.py`
- `backend/tests/test_participation_postgres.py`
- `backend/tests/test_participation_lifecycle.py`
- `backend/tests/test_participation_lifecycle_postgres.py`
- `backend/tests/test_waitlist.py`
- `backend/tests/test_waitlist_postgres.py`

Updated current documentation:

- `README.md`
- `backend/docs/activity-participation.md`
- `backend/docs/activity-check-in.md`
- `backend/docs/activity-management.md`
- `backend/docs/activity-gallery.md`
- `backend/docs/activity-finalization.md`
- `backend/docs/my-activities.md`
- `backend/docs/activity-waitlist.md`
- `backend/docs/participation-lifecycle-worker.md`

Historical milestone reports remain historical records. Final pytest warnings
were the existing Starlette/httpx deprecation, Alembic path_separator deprecation,
and denied writes to the preexisting local pytest cache; they did not fail tests.
No cache/dependency configuration changes were made for this correction.

The task-created `dk_organizer_test_20261108` database was inspected at the new head
and dropped after testing; generated migration databases were cleaned by their
fixtures. Verification logs were moved from backend/.tmp into the system temporary
directory so the working tree contains only intended deliverables. Preexisting
pytest cache files were not removed. Docker Desktop and the existing PostGIS
Compose database service were started for validation and left available. No
Compose volume removal or development database upgrade/downgrade/reset occurred.
