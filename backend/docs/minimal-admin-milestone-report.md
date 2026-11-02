# Minimal Admin milestone report

Verified 2026-10-31 against the current repository. Scope stops at minimal
administration/moderation. The backend MVP enters **FEATURE FREEZE**.

## Requested review points

| # | Item | Verified result |
| --- | --- | --- |
| 1 | Branch and HEAD | `backend`, `ecf2a09`. Initial working tree clean. No Git write operations, commit, push or PR creation. |
| 2 | Actual baseline | Before implementation: default pytest **701 passed, 167 skipped**; separate real PostgreSQL/PostGIS suite **166 passed**. Ruff, compileall and lock check passed. Source and development revision both `20261030_0011`. |
| 3 | Existing auth/admin state | Existing auth JWT access/refresh, profiles, activities, discovery, FIFO queues, worker, confirmation, PostGIS check-in, finalization, personal lists, private gallery, points and readiness hardening verified from source/tests. No admin model/router existed. Login and central access/refresh user resolution already rejected inactive users, so that behavior was preserved. |
| 4 | User model | Added non-null boolean `User.is_admin`, ORM default false, server default false. No other user fields or points semantics changed. |
| 5 | Migration | New `20261031_0012_add_user_is_admin.py`, revision `20261031_0012`, parent `20261030_0011`. Old migrations unchanged. |
| 6 | Upgrade/downgrade | Upgrade defaults all existing accounts to false and retains the false server default. Explicit NULL rejected. Downgrade drops only the column; assignments are lost. Re-upgrade sets existing users to false again. All existing user/activity/participation/photo rows preserved through the tested cycle. |
| 7 | is_admin semantics | Intentionally a simple boolean, not general RBAC. No roles, permission tables, first-user promotion, hardcoded admin identity or public promotion API. Existing bootstrap remains ordinary-user only; explicit UUID-based local SQL provisioning is documented. |
| 8 | require_admin | Reuses get_current_user and its existing token parsing/database lookup. Anonymous/invalid/inactive/deleted users return 401; active non-admin 403; active DB admin allowed. JWT privilege claims are ignored. Demotion is observed on the next request. |
| 9 | Current-user schema | UserRead now includes is_admin on GET/PATCH /users/me and registration's own-account response. It remains absent from normal register/profile request fields. |
| 10 | Public privacy | ActivityOrganizerRead and PhotoUploaderRead still contain only id/display_name/avatar_url. No public admin flag, email, password hash or participant-private timestamps. |
| 11 | Admin users endpoint | GET /api/v1/admin/users returns only id/email/display_name/is_active/is_admin/points_total/created_at. Inactive accounts included. Explicit SQL projection does not select password_hash; responses never expose it. |
| 12 | Users pagination/order | limit defaults 20, range 1..100; offset defaults 0, minimum 0. created_at ASC, UUID ASC. Tests cover tied timestamps, primary timestamp order, slices and empty pages. |
| 13 | Activation endpoint | PATCH /api/v1/admin/users/{user_id}/active accepts exactly a required boolean is_active and returns AdminUserRead. Unknown users 404. Unknown fields and non-boolean/missing/null input 422. Repeated state succeeds. |
| 14 | Self-deactivation | 409 `Administrators cannot deactivate themselves`. Self-activation succeeds. Another admin may be deactivated; no last-admin policy was added. |
| 15 | Existing tokens | Deactivated users cannot login, use pre-issued access tokens on protected APIs, or refresh pre-issued refresh tokens. Real HTTP and PostgreSQL tests verify persisted changes. Reactivation restores login and still-valid old tokens. No blacklist or revocation system. |
| 16 | Admin activities | GET /api/v1/admin/activities includes future/ongoing/ended/cancelled records, using the same limit/offset/order convention. Small AdminActivityRead includes safe organizer, status, schedule, cancellation evidence, counts and creation time; no participant lists/emails/private timestamps/caller permissions. |
| 17 | Admin cancellation | POST /api/v1/admin/activities/{activity_id}/cancel allows a non-organizer active admin, returning AdminActivityRead. Unknown 404; repeated/already-cancelled or ended, including exact end boundary, 409. No direct status-write or hard-delete operation. |
| 18 | Cancellation reuse | Calls existing activity_management_service.cancel_activity. The trusted is_admin argument relaxes ownership only. Ordinary organizer route still checks ownership. No duplicate cancellation implementation. |
| 19 | Domain invariants | Existing activity-first FOR UPDATE, refreshed state after waits, snapshot-before-commit and rollback retained. Discovery excludes cancelled activities; detail/personal history retain them. Membership/check-in evidence preserved; further participation changes, finalization and uploads blocked. Existing photo viewing/history remains governed by normal gallery rules. FIFO/worker/finalization/points/max-three locks unchanged. |
| 20 | Photo moderation | Existing DELETE /api/v1/activities/{activity_id}/photos/{photo_id} accepts uploader with normal eligibility or an active admin. Organizer alone cannot delete someone else's photo; unrelated ordinary users cannot delete. No new admin photo endpoint. Activity/photo existence and association still validated. |
| 21 | Gallery 72h distinction | Admin DELETE works at and after end_at+72h without participation or view permission. Normal GET/upload permissions are unchanged; unrelated admin GET remains 403. Ordinary uploader deletion still closes at the boundary. |
| 22 | Storage failures | Same storage-first deletion, DB delete/commit second. Safe 503 preserves metadata and object on storage failure. DB failure after object removal rolls back metadata and remains repairable by idempotent retry; tested. No credentials, keys or SDK errors are returned by moderation. |
| 23 | Security review | Register/profile inputs cannot self-promote; their existing unknown-field-ignore behavior is preserved, including server-controlled points. Admin activation rejects unknown fields. DB-based authority, inactive/demoted/unknown JWT subjects, forged privilege claim, no password_hash output, minimal organizer/activity projections, lifecycle cancellation and photo errors tested. |
| 24 | Files created | 11 files: migration, admin router/schema/service, administration contract and this report, admin_data.py, migration_data.py, test_admin.py, test_admin_postgres.py, test_admin_migration_postgres.py. Exact paths below. |
| 25 | Files modified | 20 existing files: README, auth dependency/router registration, photo/current-user route docs, OpenAPI tags, user model/schema, cancellation/gallery integration, two domain contracts and historical migration/OpenAPI fixtures. Exact paths below. |
| 26 | Documentation | README now documents routes/model/provisioning/current verification/feature freeze and corrects stale frontend status. New administration.md defines the full contract and exact frontend work. Gallery/management docs describe shared cancellation and admin-only deletion after closure. Earlier milestone reports remain historical. |
| 27 | Isolated admin tests | **59 passed** in tests/test_admin.py, including authorization for all four routes, pagination, privacy, activation/login/access/refresh, self-protection, self-promotion, JWT claims/demotion, lifecycle effects/rollback, photo ownership/expiry/existence/storage/commit failures and OpenAPI. |
| 28 | Dedicated PostgreSQL tests | **10 passed**: activation persistence and token invalidation, late photo deletion success/storage failure with independent DB observation, HTTP cancellation/evidence, both real lock acquisition orders for admin cancel versus join/organizer cancel, rollback, and generated-database migration cycle. |
| 29 | Gallery regressions | Separate gallery/storage run **68 passed, 1 skipped** (optional real MinIO smoke). Real PostgreSQL gallery max-three/contention and migration regressions also passed in the full PostgreSQL suite. Auth/gallery initial regression run **131 passed**. |
| 30 | Default pytest | `uv run pytest -v`: **760 passed, 177 skipped**, 1 existing Starlette warning. Skips are 176 PostgreSQL cases and 1 optional MinIO case. |
| 31 | PostgreSQL/PostGIS | Separate full suite **176 passed**, 30 existing warning instances. SQLite is not claimed as evidence for PostgreSQL constraints/locking/geography. |
| 32 | Ruff | `uv run ruff check .`: passed. |
| 33 | compileall | `uv run python -m compileall app`: passed. |
| 34 | uv lock | `uv lock --check`: passed; dependency files unchanged. |
| 35 | Alembic current | Source and disposable test DB: `20261031_0012 (head)`. Development DB remains `20261030_0011`, with 2 users, 1 activity, 0 participation rows and 0 photos, as before. Run `uv run alembic upgrade head` before serving updated code against development. No development migration/downgrade was performed. |
| 36 | Migration cycle | `20261030_0011 -> 20261031_0012 -> 20261030_0011 -> 20261031_0012` passed in a generated temporary PostgreSQL/PostGIS DB, verifying default/NULL behavior, explicit admin persistence, data preservation and privilege loss on downgrade. Existing historical cycles passed too. |
| 37 | Diff check | `git diff --check` passed. Existing LF/CRLF advisories and unreadable root pytest-cache warning are environmental; no suppressed warnings. |
| 38 | Git status | Branch/HEAD unchanged. Only the 20 expected modified and 11 new milestone files remain; all are backend code/tests/docs or root README. No staged changes, commit, push or PR. |
| 39 | Frontend unchanged | `git diff -- frontend` empty; no frontend file edited. |
| 40 | Exact frontend work | Add is_admin to UserProfile; admin guard/navigation; typed paginated admin clients/queries; user table/active toggle with disabled self-deactivation; activity list/admin cancel; photo delete by known activity/photo IDs; pending/error/401/403/404/409/422/503 handling, mutation invalidation and admin/gallery private-cache cleanup. Current real lifecycle/profile/auth UI remains functional. Detailed source paths and distinctions in administration.md. |
| 41 | Known limitations | Boolean admin only; no RBAC/audit log/last-admin protection. No admin photo browsing/listing, report workflow, hard deletes, points editing or privilege API. No atomic DB/S3 transaction/reconciliation/retention cleanup. Lists have no totals or cross-page snapshot. Deactivation affects subsequent requests and does not interrupt authorized work already in flight. Reactivation restores still-valid tokens. Development still needs additive upgrade. Optional real MinIO smoke not rerun. |
| 42 | Feature freeze | Minimal Admin milestone complete. Backend MVP is in **FEATURE FREEZE**. No new MVP backend features proposed or implemented beyond this scope. |

## Exact files

Created:

```text
backend/alembic/versions/20261031_0012_add_user_is_admin.py
backend/app/api/v1/admin.py
backend/app/schemas/admin.py
backend/app/services/admin_service.py
backend/docs/administration.md
backend/docs/minimal-admin-milestone-report.md
backend/tests/admin_data.py
backend/tests/migration_data.py
backend/tests/test_admin.py
backend/tests/test_admin_migration_postgres.py
backend/tests/test_admin_postgres.py
```

Modified:

```text
README.md
backend/app/api/dependencies.py
backend/app/api/router.py
backend/app/api/v1/activity_photos.py
backend/app/api/v1/users.py
backend/app/main.py
backend/app/models/user.py
backend/app/schemas/user.py
backend/app/services/activity_management_service.py
backend/app/services/gallery_service.py
backend/docs/activity-gallery.md
backend/docs/activity-management.md
backend/tests/gallery_data.py
backend/tests/test_activity_finalization_migration_postgres.py
backend/tests/test_check_in_migration_postgres.py
backend/tests/test_gallery_migration_postgres.py
backend/tests/test_lifecycle_worker_migration_postgres.py
backend/tests/test_openapi.py
backend/tests/test_participation_lifecycle_migration_postgres.py
backend/tests/test_waitlist_migration_postgres.py
```

Historical migration tests now seed reflected historical users tables rather
than emitting the current ORM's new is_admin column against old revisions.
The test-only helper preserves their previous data/constraint assertions;
no old migration or production gallery-seeding behavior was changed.

## Validation environment

Baseline completed before implementation. The existing development database
container was initially stopped. It was started for read-only revision/count
inspection and returned to its initial stopped state afterward. Development data,
schema, MinIO and named volumes were not changed.

A separate task-labelled `dk-admin-postgres-test` container used the existing
PostGIS 17/3.5 image, a disposable `dk_admin_test` database, and loopback port
55435. Migration tests created/dropped only generated temporary databases.
Final inspection showed no users/activities or leftover admin-migration database
in that test container. The task container and its anonymous volume were removed
after validation. No compose down or named-volume removal was used.

The default uv cache was inaccessible, so validation used a workspace-local cache
and `--offline` with already-installed dependencies. PostgreSQL tests additionally
needed the local Docker/network sandbox permission. Logs are retained under the
ignored `backend/.tmp/pytest_cache/minimal-admin-validation/` directory.

From backend, checks were equivalent to the requested commands:

```powershell
uv run --offline pytest -v
uv run --offline ruff check .
uv run --offline python -m compileall app
uv lock --offline --check
uv run --offline alembic current
uv run --offline pytest -v tests/test_admin.py
uv run --offline pytest -v tests/test_gallery.py tests/test_photo_storage.py tests/test_gallery_storage_integration.py
```

With POSTGRES_TEST_DATABASE_URL pointing only to the disposable database:

```powershell
uv run --offline pytest -v tests/test_admin_postgres.py tests/test_admin_migration_postgres.py
$postgresTests = @(rg --files tests -g '*postgres.py')
uv run --offline pytest -v @postgresTests
```

Final Git review used only read-only branch/status/diff/diff-check/HEAD commands.
The final deliverable is intentionally uncommitted for review.
