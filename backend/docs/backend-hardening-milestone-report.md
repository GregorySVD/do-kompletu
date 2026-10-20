# Backend hardening milestone report — 2026-10-19

Work stayed on the existing `backend` branch, starting from a clean working tree.
Repository and development database were verified at `20261019_0010` before
implementation. The requested baseline was rerun: **518 default tests passed,
146 PostgreSQL tests skipped**, and **146 separate PostgreSQL/PostGIS tests
passed**. No commit, push, merge, or rebase was performed. Frontend files were
inspected but not changed.

| # | Requested report item | Result |
| --- | --- | --- |
| 1 | Existing behavior discovered | Public discovery excluded cancelled rows but retained ended rows; check-in accepted only latitude/longitude; `/health` provided liveness without a database query; refresh caught every `Exception` and returned 401; settings allowed the fixed development JWT secret in production. Existing participation states, automatic expiry/FIFO promotion, and manual finalization were already implemented and remain unchanged. |
| 2 | Discovery filtering change | Normal `GET /api/v1/activities` now adds `cancelled_at IS NULL AND end_at > cutoff` in the SQL query before ordering/offset/limit. PUBLISHED and ONGOING remain eligible. ENDED and CANCELLED are excluded. Search/category/price filters, array shape, counts, and pagination parameters are preserved. |
| 3 | Exact discovery time semantics | Capture one timezone-aware `datetime.now(UTC)` per list request and reuse it for SQL filtering, existing ordering, and returned status projection. Exact `end_at == cutoff` is excluded; one microsecond later is eligible. Remaining records preserve start-time ascending/UUID ascending ordering. Direct detail and My Activities/history still return historical/cancelled activities under their existing rules; no activity is deleted. |
| 4 | Check-in request change | `POST /api/v1/activities/{activity_id}/check-in` now requires `{"latitude":52.4232,"longitude":16.9461,"accuracy_m":20}`. Successful response remains full ActivityRead with HTTP 200. Existing authentication, membership, timing, and spatial requirements are unchanged. |
| 5 | accuracy_m validation rules | Required finite floating-point number strictly greater than zero; unknown fields remain forbidden. Missing/null/zero/negative/nonfinite/invalid values produce 422. A RequestValidationError handler preserves the normal 422 detail structure while encoding nonfinite numbers in error inputs as strings, so raw NaN/Infinity or overflowing JSON numbers do not cause response-serialization 500 errors. There is no separate fixed schema upper bound: a structurally valid value above the configured maximum produces 409 `Location accuracy is insufficient for check-in`. Equality at the maximum is accepted. Accuracy is checked after lifecycle/time eligibility and before the PostGIS radius query. |
| 6 | Max-accuracy configuration | Added `ACTIVITY_CHECK_IN_MAX_ACCURACY_METERS=100` to Settings and `.env.example`; Settings requires a finite positive value. It is independent of `ACTIVITY_CHECK_IN_RADIUS_METERS` (default 150). Existing local `.env` need not be changed because the new setting has a default. |
| 7 | Accuracy privacy/storage behavior | Latitude, longitude, accuracy, and computed distance remain transient validation data. They are not added to participation persistence or returned as participant-location evidence. Successful check-in still records only the existing attendance timestamp/state. Public venue coordinates remain public. No database columns were added. |
| 8 | GPS-spoofing limitation | Client-reported accuracy helps reject naturally poor GPS fixes. It does not prove submitted coordinates are genuine and does not prevent spoofing. PostGIS `ST_DWithin` remains the authoritative separate radius check after accuracy validation. No anti-spoofing or device attestation was added. |
| 9 | /health semantics | Existing public `GET /health` remains lightweight API-process liveness: HTTP 200 `{"status":"ok"}` without resolving a database session or issuing SQL. |
| 10 | /ready semantics | Added public `GET /ready`: HTTP 200 `{"status":"ok"}` when the configured database can execute the probe; recognized database connectivity failures return HTTP 503 `{"detail":"Database unavailable"}`. |
| 11 | Database readiness implementation | Synchronous FastAPI route uses the existing `Depends(get_db)` SQLAlchemy session architecture and executes only `session.execute(text("SELECT 1"))`. It does not query tables, validate migrations, inspect PostGIS, or perform a schema health check. |
| 12 | Readiness failure handling | Catches SQLAlchemy `OperationalError`, `InterfaceError`, `DisconnectionError`, and pool `TimeoutError`. The client response contains no credentials, database URL, SQL exception text, or stack trace. `ProgrammingError` and unexpected application failures propagate through normal server-error handling. No broad `except Exception` was added. |
| 13 | Refresh exception bug discovered | The refresh route wrapped its complete service call in `except Exception`, incorrectly turning database/service failures into `401 Could not validate refresh token`. That made infrastructure outages look like expired credentials to clients. |
| 14 | Concrete refresh exception handling implemented | The route now catches only the application's `InvalidTokenError`, including its `ExpiredTokenError` subclass. Existing token decoding normalizes installed python-jose `JWTError`/`JWTClaimsError` and `ExpiredSignatureError` into that hierarchy. A narrow NumericDate conversion guard handles malformed `iat`/`nbf`/`exp` JSON values whose conversion can otherwise escape python-jose as TypeError/ValueError/OverflowError; authoritative signature/claims verification still follows in `jwt.decode`. Generic 401 detail and the Bearer challenge are preserved. |
| 15 | Infrastructure-error behavior after fix | SQLAlchemy failures and unexpected service/decoder failures are no longer transformed into authentication responses. They propagate to normal server-error handling; TestClient propagation tests explicitly distinguish them from 401. Refresh request/response JSON and valid-token behavior remain unchanged. |
| 16 | Production JWT validation design | Central Settings validation runs when settings/application construction occurs, before serving requests. Existing blank-secret validation remains. Production validation checks recognized unsafe placeholders and a straightforward minimum length. Settings validation text hides input values rather than printing secrets. No production-secret details were added to Swagger. |
| 17 | Production secret rules | For `ENVIRONMENT=production`, missing JWT_SECRET falls back to the known development default and is rejected. Empty/whitespace-only secrets are rejected. The known development default and `.env.example` placeholder are rejected after trimming surrounding whitespace. Other secrets must have at least 32 characters after trimming. Configure a random non-default secret; no entropy estimator is implemented. |
| 18 | Development/test behavior | Normal development/test retain the existing fixed development default and short test-secret conventions. The production minimum-length/default rejection does not impose a production-secret setup requirement locally. Existing rejection of explicitly blank secrets remains. Tests use synthetic values, never real credentials. |
| 19 | Migration status | No schema migration was required or created. Repository head remains `20261019_0010`; there is no 0011 revision. The development database was not migrated, downgraded, reset, or recreated. Final read-only checks found 2 users, 1 activity, and 0 participations; no pre-task count comparison is claimed. PostgreSQL tests ran against a separate task-created database, including generated databases for existing migration-cycle tests. No Compose volume was destroyed. |
| 20 | Files created | Four files: this report, `backend/tests/test_config.py`, `backend/tests/test_discovery_hardening.py`, and `backend/tests/test_backend_hardening_postgres.py`. Exact paths are listed below. |
| 21 | Files modified | 23 existing tracked files: Settings/environment example; activity/auth routes; JWT decoder; app health/readiness registration; check-in/activity schemas and services; relevant regression tests; README and four contracts. Exact paths are listed below. |
| 22 | Documentation changed | README documents current status, discovery/history visibility, accuracy, liveness/readiness, production settings, refresh error semantics, and verified frontend gaps. Detailed check-in contract covers request/schema/configuration, validation order, privacy, spoofing limits, errors, and frontend payload. Minimal waitlist/My Activities/lifecycle-worker edits keep discovery/current-status references consistent. OpenAPI includes `/ready`, accuracy schema/example/409, and discovery exclusion. |
| 23 | Tests added | New/extended coverage verifies discovery lifecycle inclusion/exclusion, exact boundaries, one-cutoff behavior, filtering/pagination/order/history retention; accuracy schema/limit/boundaries/rollback/transience and real PostGIS checks; readiness SQL count/connectivity errors/non-disclosure/liveness independence/programming-error propagation; valid and invalid refresh tokens/claims/library errors/infrastructure failures; and production versus development/test secret rules/startup rejection. Existing lifecycle/finalization/waitlist check-in fixtures now supply required accuracy without changing their original scenario. Detailed coverage is listed below. |
| 24 | Default pytest result | Final `uv run pytest -v`: **613 passed, 153 skipped**, one existing Starlette TestClient/httpx deprecation warning, in 41.11 seconds. Baseline was 518 passed / 146 skipped. All final NumericDate and nonfinite validation-response changes are included. |
| 25 | PostgreSQL/PostGIS result | Separate final `uv run pytest -v @testFiles` across all fifteen `*postgres.py` modules: **153 passed**, 22 existing warnings, in 41.12 seconds. Baseline was 146 passed. Includes actual PostGIS accuracy/privacy, discovery timezones, normal-session readiness, locking, and existing migration cycles. |
| 26 | Ruff result | Final `uv run ruff check .`: **passed** (`All checks passed!`). |
| 27 | compileall result | Final `uv run python -m compileall app`: **passed**. |
| 28 | uv lock result | Final `uv lock --check`: **passed**, 66 packages resolved. No dependency/lockfile changes were required. |
| 29 | Alembic current | `uv run alembic current`, `uv run alembic heads`, and a direct development-database query all confirm `20261019_0010 (head)`. No migrations were changed. |
| 30 | git diff --check | Final `git diff --check`: **passed**. Existing Git LF/CRLF notices are separate from whitespace errors. |
| 31 | git status --short | Intended 23 modified tracked files and four new files, listed in the status snapshot below. Work remains uncommitted on `backend`; no commit/push/merge/rebase was performed. |
| 32 | Confirmation frontend unchanged | No frontend file was written. Final `git diff -- frontend` from the repository root is **empty**. |
| 33 | Exact frontend integration changes | Add a check-in payload/API/mutation and browser geolocation flow sending latitude, longitude, and `accuracy_m: position.coords.accuracy`; handle poor-accuracy 409 in addition to existing radius/window errors. Discovery receives no ENDED/CANCELLED rows without a client change. Readiness normally needs no UI integration; the existing gate still calls liveness `/health`. Refresh JSON remains unchanged. Existing session restoration clears tokens on any failure, so distinguishing network/5xx from authentication rejection remains optional client resilience work. Full existing participation/personal-list/caching integration is still outstanding. Exact source observations are below. |
| 34 | Remaining known backend limitations | Accuracy is self-reported and spoofable. Readiness proves database connectivity only, not migrations/PostGIS/schema readiness. JWT refresh remains stateless, with no rotation/revocation/logout endpoint. Lifecycle automation still depends on running app workers and its existing sweep/lock lag; finalization remains manual. No new scheduler/product features, notifications, rewards, payments, audit history, or attendance overrides were added. Existing broader limitations are retained in README. |
| 35 | Ready for frontend integration? | **Yes, for the current API and documented scope.** All required checks passed. The five requested backend changes are implemented; frontend code remains unchanged and the required check-in request change is documented. Existing frontend participation/history/cache integration still needs implementation. |

## Exact file inventory and status

Created:

- `backend/docs/backend-hardening-milestone-report.md`
- `backend/tests/test_backend_hardening_postgres.py`
- `backend/tests/test_config.py`
- `backend/tests/test_discovery_hardening.py`

Modified files are shown in the working-tree snapshot. `M` means modified and
`??` means newly created/untracked; these changes have not been committed.

```text
 M README.md
 M backend/.env.example
 M backend/app/api/v1/activities.py
 M backend/app/api/v1/auth.py
 M backend/app/core/config.py
 M backend/app/core/security.py
 M backend/app/main.py
 M backend/app/schemas/activity.py
 M backend/app/schemas/activity_check_in.py
 M backend/app/services/activity_service.py
 M backend/app/services/participation_service.py
 M backend/docs/activity-check-in.md
 M backend/docs/activity-waitlist.md
 M backend/docs/my-activities.md
 M backend/docs/participation-lifecycle-worker.md
 M backend/tests/test_activity_finalization.py
 M backend/tests/test_activity_finalization_postgres.py
 M backend/tests/test_auth.py
 M backend/tests/test_check_in.py
 M backend/tests/test_check_in_postgres.py
 M backend/tests/test_health.py
 M backend/tests/test_lifecycle_worker.py
 M backend/tests/test_waitlist.py
?? backend/docs/backend-hardening-milestone-report.md
?? backend/tests/test_backend_hardening_postgres.py
?? backend/tests/test_config.py
?? backend/tests/test_discovery_hardening.py
```

## Regression coverage

- Discovery: future PUBLISHED and current ONGOING included; exact-end/earlier ENDED
  and CANCELLED excluded; direct historical/cancelled detail remains readable;
  organized/joined history remains visible; search/category/price filters and
  limit/offset retain deterministic order; omitted lifecycle rows do not enter
  discovery results. An advancing clock proves the service reads one UTC cutoff.
  PostgreSQL tests cover microsecond boundaries with offset timestamps and
  non-UTC session timezones, using a unique fixture marker to avoid unrelated data.
- Accuracy: required/unknown-field/schema errors; zero/negative/nonfinite values;
  raw NaN/Infinity/-Infinity and overflowing JSON numbers retain 422 rather than
  failing when validation error inputs are serialized;
  configurable accepted values, exact maximum, and just-above rejection; poor
  accuracy rejected before any proximity query; failed requests preserve state;
  Swagger schema/examples/errors and eligibility-only `can_check_in` semantics.
  Real PostGIS tests verify inside/outside radius with usable accuracy, poor
  accuracy rejected even at the venue, and no submitted location/accuracy stored.
  Existing spatial, antimeridian, lock/concurrency, count, privacy, and lifecycle
  regressions continue using the required request field.
- Readiness: exactly one `SELECT 1`, successful JSON, each concrete connectivity
  exception mapped to safe 503, no connection/SQL leakage, `/health` independent of
  the database dependency, programming/unexpected failures propagated, OpenAPI,
  and a real PostgreSQL request through the normal configured session factory.
- Refresh: valid, expired, malformed, wrong-type, invalid-signature, invalid subject
  or other authentication claims; installed python-jose decode exception classes;
  malformed null/list/object/nonfinite NumericDate values; supported integer,
  finite-float, and integer-string NumericDate compatibility; database/service and
  unexpected decoder exceptions propagated rather than turned into 401.
- Settings: development/test default and short-secret compatibility; production
  missing/blank/default/example/short-secret rejection; whitespace-aware minimum;
  valid non-default secrets at/above 32 characters; settings error text does not
  echo the secret; application construction fails before serving requests.

## Exact frontend observations and follow-up

1. `frontend/src/api/activitiesApi.ts` currently provides list/categories/detail/
   creation only. Add a typed check-in request and mutation for the existing
   endpoint. No browser geolocation utility currently exists. Use
   `position.coords.latitude`, `position.coords.longitude`, and
   `accuracy_m: position.coords.accuracy`; handle denied permission, timeout,
   unavailable position, poor accuracy, and normal lifecycle/radius conflicts.
2. `frontend/src/hooks/useActivityFilters.ts` has local search/category/price/
   time/availability filters but no manual ENDED/CANCELLED removal. No lifecycle
   filter needs removal for this milestone. The API list still requests only
   `limit=100, offset=0`; broader pagination/filter integration remains existing work.
3. `frontend/src/api/healthApi.ts` and `BackendStatusGate.tsx` call `/health`.
   They continue to check API liveness. `/ready` is available to deployment probes;
   changing the UI gate to database readiness is optional, not required here.
4. `frontend/src/api/authApi.ts` keeps the same refresh payload/response. In
   `frontend/src/context/AuthContext.tsx`, session restoration currently clears
   stored tokens on every refresh failure, including network/5xx failures. Future
   client work may preserve the session during transient outages and reserve
   authentication handling for 401; no such frontend change was made here.
5. `frontend/src/types/activity.ts` still types current participation as exactly
   null; existing membership/expiry/final-outcome types, actions, real My Activities,
   user-scoped caches, mutation invalidation, and lifecycle refetch work from the
   previous milestone remain outstanding. Add accuracy when implementing check-in,
   and invalidate affected detail/discovery/personal queries after success.

The [README](../../README.md), [check-in contract](activity-check-in.md), and
[lifecycle contract](participation-lifecycle-worker.md) describe the current API
and existing lifecycle/deployment constraints.

PostgreSQL baseline/final validation used the isolated
`dk_hardening_test_20261019` database on the existing healthy PostGIS development
container. Tests use rollback fixtures or generated records with targeted cleanup;
existing migration-cycle tests create/drop their own temporary databases. The
normal development database was inspected read-only, and no development migration
or persistent-volume reset was needed. Only the task-created test database was
dropped after validation; a catalog query confirmed it no longer exists. Final
development revision remains `20261019_0010`, with the same observed 2 users,
1 activity, and 0 participations from the earlier read-only final check.
