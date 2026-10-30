# Gallery milestone report — 2026-10-30

Gallery backend is ready for commit/review. No commit, push, branch change, fetch,
PR or other Git write operation was performed. Frontend files are unchanged.
The full API/local-storage/frontend contract is in [activity-gallery.md](activity-gallery.md).

## Requested 50-point review

| # | Item | Actual result |
| --- | --- | --- |
| 1 | Branch and HEAD | `backend`; starting and final HEAD `5b72e5d`. Initial working tree was clean. |
| 2 | Baseline | Before implementation: 613 default tests passed, 153 PostgreSQL tests skipped; separate isolated PostgreSQL/PostGIS run 153 passed. Ruff, compileall and uv lock passed. Actual migration files and development DB verified at `20261019_0010`. Initial cache/Docker permission restrictions and a stopped DB were resolved with a workspace cache and authorized Docker access; the existing DB volume was retained. |
| 3 | Existing placeholders | Backend gallery booleans defaulted to false. Frontend already declared both booleans but had no photo DTO, photo API, gallery UI or upload placeholder. Existing lifecycle functions/hooks and identity-scoped detail queries are already implemented; older frontend summaries are stale. |
| 4 | Files created | 18 files, listed below. |
| 5 | Files modified | 28 files, listed below; backend/README/docs only. Existing migration files were not changed. |
| 6 | Dependencies | Added missing `boto3>=1.43.123` and `pillow>=13.0.0` using uv add. Lock adds boto3, botocore, jmespath, Pillow, python-dateutil and s3transfer. python-multipart was already supplied by FastAPI standard and was not added again. |
| 7 | Migration | `20261030_0011_create_activity_photos.py`, based on verified `20261019_0010`. |
| 8 | Upgrade/downgrade | Upgrade creates only gallery metadata/constraints/indexes. Downgrade drops only that table and cannot delete external objects. Existing users/activities/participations preserved, including exact row comparisons. Gallery metadata is intentionally lost on downgrade. |
| 9 | ActivityPhoto | UUID PK, activity/uploader UUID FKs, unique object key, validated MIME, integer byte size, aware created_at. No image binary, stored URL, original path/name or secrets. |
| 10 | Indexes/constraints | Composite activity_id/uploader_id index supports gallery/quota lookup; separate uploader index supports FK lookup; no redundant standalone activity index. Unique object key; non-null fields; MIME and 1..10,485,760 byte CHECKs; RESTRICT FKs preserve external-object metadata during hypothetical hard deletion. |
| 11 | Storage abstraction | PhotoStorage protocol with put/delete/presigned_get_url; S3PhotoStorage owns all boto3 object operations. Injectable fake and SDK Stubber tests. No I/O at API startup. |
| 12 | S3/MinIO config | Six requested S3 variables in Settings and `.env.example`; credentials use SecretStr. Default TTL 300, validated 1..900. Compose adds a loopback-only local MinIO service and separate persistent volume while preserving PostgreSQL. |
| 13 | Local workflow | `uv sync --frozen`, add example storage values to existing `.env`, `docker compose up -d --build`, wait for healthy, `uv run python -m app.scripts.init_photo_storage`, then normal Alembic/API commands. Explicit idempotent bucket setup avoids coupling startup to storage. |
| 14 | Object keys | `activities/{activity_uuid}/{random_photo_uuid}.{validated_extension}`. Original filename ignored and never persisted. |
| 15 | Image validation | Pillow restricts detected format, matches declared MIME, verifies structure and fully decodes all frames; generic 422 for invalid/corrupt/decompression-bomb images. JPEG, PNG, WebP accepted; GIF/SVG/PDF/arbitrary data/octet-stream rejected. Bytes are not transformed. |
| 16 | File size | Central inclusive 10,485,760-byte constant; spooled UploadFile stream read in <=64 KiB chunks, stopping at limit+1 with 413. Exact boundary and bounded read position tested. |
| 17 | View | Authenticated CHECKED_IN/COMPLETED participant or organizer, strictly before end_at+72h. All other callers denied. |
| 18 | Upload | CHECKED_IN/COMPLETED only, strictly before closure, uncancelled, current own count <3. |
| 19 | Organizer | May view without participation; identity alone grants no upload. Can never delete another uploader's photo. Explicitly eligible participation would grant the ordinary upload rule, without changing existing organizer join restrictions. |
| 20 | Cancellation | Preserves existing objects/metadata and eligible view/delete; denies new upload. No cancellation-triggered cleanup. |
| 21 | Boundary | Central aware UTC calculation; `now == end_at + 72h` and later deny GET/POST/DELETE and both permission flags. Before/after end and exact closure covered without sleeps as clocks. |
| 22 | Max three | Counts current metadata under the activity row lock, then puts/inserts/commits while holding that lock. Fourth upload returns 409; another eligible user has an independent allowance. Successful deletion frees a slot. |
| 23 | Concurrency | Existing activity-first FOR UPDATE, populate_existing and production READ COMMITTED conventions reused. Clock/status checked after acquiring lock and again around validation/storage. Real tests observe PostgreSQL lock waiters. |
| 24 | Upload consistency | Validate/put/insert/flush/sign/commit. Errors roll back and attempt object deletion, including ambiguous PUT failure. Failed compensation logs only generated key for operational cleanup and preserves original error. Process crashes/ambiguous commit acknowledgements remain a documented cross-system limitation. |
| 25 | GET | Protected array of typed DTOs, ordered created_at ASC/id ASC, uploader eager joined, per-item fresh signed URL. |
| 26 | POST | Protected multipart `file`, typed photo DTO, 201. Swagger binary upload schema and errors documented/tested. |
| 27 | DELETE | Protected activity/photo association + uploader + normal view access; storage first, then metadata, 204. No moderation/admin API. |
| 28 | Delete failures | Transient storage failure returns sanitized 503 and preserves row. Missing S3 key is idempotently successful. DB failure after object removal preserves row via rollback, logs photo UUID and can be retried. Unknown/mismatched photo returns 404. |
| 29 | Signed URLs | SigV4 GET, on demand, TTL=min(configured TTL, remaining seconds) with one-second minimum while still open. Not persisted. URLs are bearer capabilities; second granularity can leave a subsecond overlap after API closure. No public object ACL. |
| 30 | can_view_gallery | ActivityRead and endpoints call the same can_view_activity_gallery helper. Anonymous flags false and no photo data in public detail/discovery. |
| 31 | can_upload_photo | ActivityRead and POST share can_upload_activity_photo. Flag expresses eligibility; actual quota remains transactional POST validation. |
| 32 | Privacy/security | Existing active-user access JWT required; refresh token rejected. Uploader DTO exposes only id/display_name/avatar_url. No standalone object key, private user data or storage secrets. Original filenames ignored; storage/library failures sanitized. Private/no-store responses. |
| 33 | Queries/N+1 | Eager joined uploader with only public columns. Gallery regression records four SELECTs including authentication with multiple photos, no per-photo user query. |
| 34 | Isolated tests | 61 gallery tests cover all listed participation states, organizer/anonymous/unrelated users, time/cancellation, quota, formats/size/corruption, order/privacy/query count, ownership and consistency failures. |
| 35 | PostgreSQL concurrency | Five real lock tests: two photos/two attempts -> one success; three photos/two attempts -> both denied; different users -> each reaches three; exact closure while waiting -> denied; cancellation while waiting -> denied. |
| 36 | Fake/mock storage | FakeStorage records put/delete/sign and injects failures. Seven adapter/config tests use Stubber/local signing without network, and verify private write parameters, delete behavior, sanitization/config and TTL. |
| 37 | Compose/MinIO | Compose config passed, source image built successfully, both services healthy, bucket setup run twice successfully. Optional real storage API smoke passed: upload, signed image GET, unsigned 403, gallery listing, successful delete and empty bucket. |
| 38 | Default pytest | `uv run pytest -v`: **681 passed, 160 skipped** (159 PostgreSQL, 1 optional MinIO), 1 existing Starlette warning. |
| 39 | PostgreSQL/PostGIS | Separate full suite on isolated test database: **159 passed**. No tests relied on real AWS. |
| 40 | Ruff | `uv run ruff check .`: passed. |
| 41 | Compile | `uv run python -m compileall app`: passed. |
| 42 | Lockfile | `uv lock --check`: passed, 72 packages resolved; updated only through uv. |
| 43 | Current revisions | Development DB read-only inspection: `20261019_0010` (left unmigrated). Disposable test DB after upgrade: `20261030_0011 (head)`. Source head: `20261030_0011`. |
| 44 | Migration cycle | Generated temporary PostGIS DB: 0010 -> 0011 -> 0010 -> 0011 passed, with metadata shape, indexes, FKs, uniqueness/MIME/size constraints and existing-row preservation checks. No downgrade touched the development DB. |
| 45 | Diff check | `git diff --check`: passed. Existing LF/CRLF advisory messages and unreadable root pytest-cache warning are environmental, not failing checks. |
| 46 | Git status | Only the 28 modified and 18 new intended files listed below; unstaged/untracked for review. No Git writes. HEAD unchanged. |
| 47 | Frontend unchanged | `git diff -- frontend`: empty. No frontend file edited or generated. |
| 48 | Remaining frontend work | Add photo DTO/API/query, gallery view, multipart upload, size/type/quota hints, both existing permission flags, signed image URL refresh, uploader-only deletion, exact 72h/cancellation handling, invalidation/auth cache handling and errors. Exact verified contract/steps in activity-gallery.md. |
| 49 | Known limitations | No automated retention/reconciliation, crash-proof cross-system transaction, moderation, thumbnails, image rewriting or frontend. Signed URLs cannot revoke downloaded bytes. Activity writes serialize during bounded storage I/O. MinIO community is source-only/archived; included source build is for local development. Provision production private storage separately. |
| 50 | Ready for review | Yes, Gallery backend milestone only, validated and ready for user commit/review. Deployment still requires storage settings/private bucket and normal forward migration. No commit/push; no points/admin work started. |

## Created files (18)

```text
backend/alembic/versions/20261030_0011_create_activity_photos.py
backend/app/api/v1/activity_photos.py
backend/app/models/activity_photo.py
backend/app/schemas/activity_photo.py
backend/app/scripts/init_photo_storage.py
backend/app/services/gallery_rules.py
backend/app/services/gallery_service.py
backend/app/services/photo_storage.py
backend/app/services/photo_validation.py
backend/docker/minio/Dockerfile
backend/docs/activity-gallery.md
backend/docs/gallery-milestone-report.md
backend/tests/gallery_data.py
backend/tests/test_gallery.py
backend/tests/test_gallery_migration_postgres.py
backend/tests/test_gallery_postgres.py
backend/tests/test_gallery_storage_integration.py
backend/tests/test_photo_storage.py
```

## Modified files (28)

```text
README.md
backend/.env.example
backend/app/api/router.py
backend/app/api/v1/activities.py
backend/app/core/config.py
backend/app/main.py
backend/app/models/__init__.py
backend/app/schemas/activity.py
backend/app/schemas/activity_management.py
backend/app/schemas/my_activities.py
backend/app/services/activity_service.py
backend/compose.yaml
backend/docs/activity-check-in.md
backend/docs/activity-finalization.md
backend/docs/activity-management.md
backend/docs/activity-participation.md
backend/docs/my-activities.md
backend/pyproject.toml
backend/tests/test_activity_finalization.py
backend/tests/test_activity_management.py
backend/tests/test_activity_management_postgres.py
backend/tests/test_check_in.py
backend/tests/test_check_in_postgres.py
backend/tests/test_my_activities.py
backend/tests/test_my_activities_postgres.py
backend/tests/test_openapi.py
backend/tests/test_participation.py
backend/uv.lock
```

Earlier attendance/management tests were updated only where the previous
all-permissions-false assertion conflicted with the new gallery contract. They
still assert that existing attendance mutations are blocked, and now check the
exact eligible gallery flags. Historical Swagger examples and relevant docs were
updated likewise. No existing participation/lifecycle/worker/GPS logic changed.

The temporary test PostgreSQL container/data and generated work cache/logs were
removed after verification. Development PostgreSQL/MinIO and their named volumes
remain available. No `docker compose down -v` was used. Existing `.env` was not
overwritten; copy the documented gallery settings into it before normal API use.
