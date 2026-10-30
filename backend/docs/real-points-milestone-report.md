# Real Points milestone report — 2026-10-30

Real Points is ready for commit/review. Only new CHECKED_IN -> COMPLETED
transitions award +10, within the existing finalization transaction. No frontend,
gallery, dependency, database-schema or migration changes were made. No Git write
operations, commit, push or PR creation were performed.

## Requested 35-point review

| # | Item | Verified result |
| --- | --- | --- |
| 1 | Branch and HEAD | `backend`, starting/final HEAD `290eb1b`. Initial working tree clean. |
| 2 | Actual baseline | Before implementation: `uv run pytest -v` **681 passed, 160 skipped**; separate PostgreSQL/PostGIS **159 passed**. Ruff, compileall and uv lock passed. Source/development database head verified as `20261030_0011`. A temporary uv cache worked around the existing default-cache permissions. |
| 3 | Existing points_total | User already has Integer, NOT NULL, SQLAlchemy insertion default 0. Actual PostgreSQL column is INTEGER NOT NULL without a separate server default; ORM registration uses the default. UserRead already returns it through registration, GET/PATCH /users/me. Public organizer/photo-uploader projections do not include it. No pre-existing award mutation was found. |
| 4 | Existing finalization | Organizer-only POST, same activity-first FOR UPDATE/READ COMMITTED protocol as other writers. Ownership/cancellation/end-time checks; one bulk CASE attendance UPDATE, response snapshot and one commit; any exception rolls back. Existing COMPLETED/NO_SHOW/LEFT/waitlist/expired rows excluded. Repeats return 409. |
| 5 | Business rule | The sole award source is a new CHECKED_IN -> COMPLETED transition during valid organizer finalization: +10 points per participant. No join, confirmation, check-in, waitlist/promotion, creation or other point source. |
| 6 | Central constant | `COMPLETED_ACTIVITY_POINTS = 10` in `app/services/participation_rules.py`. No environment variable or client-controlled amount. |
| 7 | Award behavior | The attendance UPDATE now RETURNINGs user_id and new status. Only returned COMPLETED rows enter the point increment; they were CHECKED_IN under the transition mapping. Deactivated participants remain eligible for their legitimate attendance outcome. |
| 8 | NO_SHOW | JOINED/CONFIRMED -> NO_SHOW gets +0. Existing NO_SHOW also stays unchanged. LEFT, WAITLISTED and both expiry statuses get +0. |
| 9 | Cancellation | Existing cancellation guard still returns 409 before transitions or points. Preserved CHECKED_IN evidence does not itself award anything. |
| 10 | Organizer | No award merely for organizing/finalizing. Organizer balance stays unchanged in normal API flows; existing organizer participation restrictions remain unchanged. |
| 11 | Existing balance | Atomic SQL addition preserves the existing balance, e.g. 30 -> 40. It never sets the balance to 10. Concurrent completion of different activities for one user preserves both increments, tested as 30 -> 50. |
| 12 | Transaction | Attendance UPDATE, optional bulk user UPDATE and response projection occur before the same single commit. No intermediate commit, outside-transaction side effect or reward endpoint. |
| 13 | Exactly once | Only actual current UPDATE winners are rewarded. Existing COMPLETED rows cannot enter the UPDATE filter. Repeated requests or retries after a lost committed response return existing 409 semantics without another increment. No scan of historical COMPLETED rows. |
| 14 | Concurrent finalization | Existing parent activity lock serializes requests; attendance is evaluated in SQL after acquiring the lock. Real concurrent HTTP tests observe both PostgreSQL lock waiters and get one 200/one 409; eligible users each receive +10, never +20. Pre-lock cached user/participation objects do not determine the award. |
| 15 | Rollback | Injected failures at point UPDATE, response snapshot and before commit leave both states/balances unchanged. Real PostgreSQL failure after observing the increment and COMPLETED status also rolls both back; a later valid retry awards once. |
| 16 | Query/performance | Still three SELECTs including authentication, one attendance UPDATE, at most one users UPDATE. Point UPDATE skipped when no checked-in winner exists. Tests cover 1/80 isolated and 1/120 PostgreSQL participants in JOINED-only and CHECKED_IN cases. No per-user SELECT/UPDATE or refresh loop. |
| 17 | Schema/migration | No migration required. No `0012`, no new table/column/index/ledger. Existing model default and non-null integer support this increment. Head remains `20261030_0011`; no development data changed. |
| 18 | Files created | Three files: two test modules and this report; exact paths below. |
| 19 | Files modified | Twelve existing files listed below: two service files, existing API/schema documentation, two finalization tests, README and relevant contracts. |
| 20 | Documentation | README now explains real aggregate points and actual validation. Finalization documents eligibility, inactive users, atomic awards, idempotency, no ledger/backfill and frontend refetch. Participation/check-in/My Activities clarify that only finalization awards points. Historical milestone reports are retained as historical records. |
| 21 | OpenAPI | Existing finalize description now states +10/+0, retry/cancellation/inactive-user behavior and /users/me refetch. No new body, wrapper, endpoint or internal lock/query description. UserRead describes server-controlled points. Personal-activities description no longer claims rewards are absent. |
| 22 | Isolated tests | **18 new point cases**, plus two new awarding query-count variants in existing finalization tests. Combined targeted points/finalization run: **69 passed**. Coverage includes all statuses, two winners, balances, next-request profile, inactive user, repeat/lost-response retry, cancellation, eligibility failures, three rollback stages and forged client fields. |
| 23 | PostgreSQL tests | Dedicated new module **5 passed** separately: concurrent HTTP finalize with one winner, several winners, existing balance; real rollback after points; concurrent different activities sharing one recipient. Existing query regression adds two CHECKED_IN size variants. SQLite is not used as evidence for concurrency. |
| 24 | Final default pytest | `uv run pytest -v`: **701 passed, 167 skipped**, 1 existing Starlette deprecation warning. Skips: 166 PostgreSQL cases and 1 opt-in MinIO case. |
| 25 | Final PostgreSQL/PostGIS | Separate full suite on disposable PostgreSQL/PostGIS: **166 passed**. Existing geometry, gallery, lifecycle, waitlist, cancellation, finalization and temporary migration-cycle coverage remains green. |
| 26 | Ruff | `uv run ruff check .`: passed. |
| 27 | Compile | `uv run python -m compileall app`: passed. |
| 28 | Lock/dependencies | `uv lock --check`: passed, 72 packages. pyproject.toml/uv.lock unchanged; no dependency added. |
| 29 | Alembic current | Development database and source head verified at `20261030_0011`; disposable test database likewise. No development migration/downgrade was performed for points. |
| 30 | Diff check | `git diff --check`: passed. Existing LF/CRLF advisories and unreadable root pytest cache warning remain environmental. |
| 31 | Git status | Twelve modified files, three intended untracked files, nothing staged; HEAD unchanged. No fetch/pull/branch operation, staging, commit, push or PR. |
| 32 | Frontend unchanged | `git diff -- frontend`: empty. Gallery service/rules/storage/validation, migrations and dependency files also have empty diffs. |
| 33 | Frontend work | Existing types/rendering already support points; AuthContext snapshot needs GET /users/me refresh on profile entry/focus or observed finalization. Details below. No reward DTO/API is required. |
| 34 | Known limitations | Aggregate balance without award ledger/history, automatic backfill, levels/ranks, undo/refunds or automatic finalization. Old COMPLETED rows are not rewarded retroactively. Exactly-once assumes terminal states through the normal service; direct SQL resets or old migration restores require balance reconciliation. |
| 35 | Readiness | Ready for Real Points commit/review. Scope stops here: no admin/moderation, gallery behavior changes, ledger, future rewards or frontend implementation. No commit/push performed. |

## Exact files

Created:

```text
backend/tests/test_points.py
backend/tests/test_points_postgres.py
backend/docs/real-points-milestone-report.md
```

Modified:

```text
README.md
backend/app/api/v1/activities.py
backend/app/api/v1/users.py
backend/app/schemas/user.py
backend/app/services/activity_management_service.py
backend/app/services/participation_rules.py
backend/docs/activity-check-in.md
backend/docs/activity-finalization.md
backend/docs/activity-participation.md
backend/docs/my-activities.md
backend/tests/test_activity_finalization.py
backend/tests/test_activity_finalization_postgres.py
```

## Frontend inspection and exact follow-up

The current frontend already has:

- `UserProfile.points_total: number` in `src/types/auth.ts`.
- A real points display, `{user.points_total}`, in ProfilePage.
- `getCurrentUser()` for GET /users/me, with existing bearer/refresh handling.
- AuthContext `refreshUser()` and `syncUserProfile()`; profile is stored in React
  context state, independently of TanStack activity queries.
- A real organizer finalize API/action and useFinalizeActivityMutation. On success
  it updates detail and invalidates discovery/personal activity queries; it does
  not refresh AuthContext's user. ProfilePage has no profile entry/focus refetch.

Required integration, with no frontend changes in this milestone:

1. Refetch GET /users/me via the existing refreshUser mechanism when entering or
   returning focus to the profile, and after observing successful final attendance
   for the current participant. Preserve current identity/session checks when
   applying asynchronous responses.
2. Keep current activity-query invalidations after organizer finalization. Adding
   profile refresh to the organizer's success path can refresh their own balance,
   but the organizer receives zero for organizing; it cannot update a participant
   in another session. Participant profile refresh is the important path.
3. Render the returned aggregate balance through the existing points display.
   No new UserProfile property, points mutation API, ActivityRead wrapper or
   organizer reward summary is needed. Do not compute or add 10 in the client.
4. Treat profile-refetch errors independently from a successful finalization.
   Retrying a profile read is safe; retrying finalize after an already committed
   result retains 409 and never awards again. No notifications/push are added.

## Validation environment and commands

All baseline tests completed before implementation. A separately named
`dk-points-postgres-test` container used a disposable `dk_points_test` database on
loopback port 55434. It used the existing PostGIS image, not the development data
volume. Old migration-cycle tests created/dropped only their generated databases.
The temporary test container and its anonymous volume were removed after checks;
development PostgreSQL/MinIO and their named volumes were retained. No
`docker compose down -v` was used.

From backend, normal final checks were:

```powershell
uv run pytest -v
uv run ruff check .
uv run python -m compileall app
uv lock --check
uv run alembic current
```

Using the disposable database's `POSTGRES_TEST_DATABASE_URL`:

```powershell
uv run pytest -v tests/test_points_postgres.py
$postgresTests = @(rg --files tests -g '*postgres.py')
uv run pytest -v @postgresTests
```

Ordinary point tests require neither AWS, internet nor MinIO. The existing real
MinIO smoke test remains opt-in and was not rerun for points-only changes.
The full PostgreSQL run reports existing Starlette, Alembic path_separator and
pytest-cache permission warnings; no warnings were suppressed. The full current
points contract is in [activity-finalization.md](activity-finalization.md#completion-points).
