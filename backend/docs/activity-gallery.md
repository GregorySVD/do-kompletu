# Private activity gallery

The Gallery milestone implements backend photo metadata and private S3-compatible
storage. Frontend files are unchanged. Minimal admin deletion was added by the
[administration milestone](administration.md); automatic cleanup remains absent.

## Access and lifecycle

`gallery_rules.gallery_closes_at(activity)` centralizes the timezone-aware UTC
deadline `end_at + 72 hours`. Access requires `now < deadline`; equality is closed.
The same helpers generate ActivityRead permissions and authorize photo operations.

| Caller | View | Upload | Delete |
| --- | --- | --- | --- |
| CHECKED_IN / COMPLETED | Until closure | Until closure, unless cancelled | Own photos while gallery view access remains |
| Organizer without eligible participation | Until closure | No | No deletion of other users' photos |
| Active admin | Normal eligibility only | Normal eligibility only | Any existing photo by activity/photo UUID, even after closure |
| All other participation states / unrelated user | No | No | No |
| Anonymous | 401 | 401 | 401 |

Cancellation preserves photos, metadata, check-in evidence and eligible viewing;
it blocks new uploads. The uploader can still delete within normal gallery access.
Closure denies normal GET, POST and DELETE and makes both ActivityRead gallery
permissions false. Admin moderation DELETE remains allowed without gallery view
permission; it grants no browsing access. Closure and cancellation never remove
stored content automatically.
`can_upload_photo` expresses eligibility; the POST additionally checks the current
quota. A caller with three existing photos receives 409 until they delete one.
Existing join/confirmation/waitlist/check-in/finalization rules are unchanged.

## API

All routes require an active user's access JWT using the existing OAuth2 bearer
dependency. Authenticated ineligible users receive 403. Successful responses and
gallery business/storage errors use `Cache-Control: private, no-store` and
`Vary: Authorization`. Public detail/discovery never contains photo metadata/URLs.

| Method | Path | Success |
| --- | --- | --- |
| GET | `/api/v1/activities/{activity_id}/photos` | 200, array ordered `created_at ASC, id ASC` |
| POST | `/api/v1/activities/{activity_id}/photos` | 201, one photo DTO |
| DELETE | `/api/v1/activities/{activity_id}/photos/{photo_id}` | 204, empty body |

POST accepts `multipart/form-data`, required field `file`. Swagger includes a
binary file control. Example from PowerShell with a locally obtained access token:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/activities/ACTIVITY_UUID/photos" -H "Authorization: Bearer ACCESS_TOKEN" -F "file=@photo.jpg;type=image/jpeg"
```

Each GET item and the POST response has exactly this shape:

```typescript
interface ActivityPhoto {
  id: string
  activity_id: string
  uploader: { id: string; display_name: string; avatar_url: string | null }
  created_at: string
  content_type: 'image/jpeg' | 'image/png' | 'image/webp'
  size_bytes: number
  url: string
}
```

`url` is an expiring presigned GET, generated on demand; it is never persisted.
No separate `object_key`, uploader email, password hash, points or private profile
fields are returned. Signed URLs necessarily contain the object path and signing
identifier; treat the complete URL as a bearer capability and do not log it.

Errors use the existing `{ "detail": ... }` convention (framework validation can
return its usual detail array): 401 authentication, 403 eligibility/closure/ownership,
404 activity/photo absent or activity/photo mismatch, 409 max-three quota,
413 oversized upload, 422 missing/invalid image or MIME mismatch, 503 storage
unavailable. Storage errors are sanitized. Database failures follow the existing
server-error handling after rollback/compensation.

## Image validation and keys

Only declared `image/jpeg`, `image/png`, `image/webp` are accepted. Pillow identifies
the actual format, checks MIME agreement, verifies image structure and decodes all
frames. Corrupt/truncated payloads and decompression bombs are rejected with a
generic error. GIF, SVG, PDFs, video, arbitrary bytes and octet-stream declarations
are rejected. Filenames/extensions do not establish format or storage location.
Accepted bytes are preserved; no resizing, recompression or metadata stripping.

The centralized inclusive limit is **10,485,760 bytes (10 MiB, called 10 MB in the
API)**. The application reads UploadFile's spooled stream in chunks of at most
64 KiB and stops at limit + 1. The exact boundary is tested deterministically.
Multipart parsing may spool to disk before route execution; deployments can also
set proxy request limits for transport/disk protection.

Keys are `activities/{activity_uuid}/{random_photo_uuid}.{jpg|png|webp}`.
The extension comes from validated content. Original filenames are never stored.

## Metadata, queries and concurrency

`ActivityPhoto` stores UUID id, activity/uploader FKs, unique object_key, MIME,
integer byte size and timezone-aware created_at. No binary data/URLs/credentials.
FKs use RESTRICT: future hard deletion must explicitly clean external objects,
instead of losing their metadata through a cascade. No hard-delete API is added.
CHECKs enforce 1..10,485,760 bytes and the three supported MIME values.

The `(activity_id, uploader_id)` index serves both activity listing and quota
counting; a separate activity_id index would duplicate its leading prefix.
`uploader_id` has its own index for FK checks/future uploader cleanup. The unique
object key has its own uniqueness backing index. GET eager-joins uploaders and
loads only id/display_name/avatar_url. Regression coverage records four SELECTs
including authentication, independent of photo count; no per-photo user SELECT.

POST and DELETE reuse `get_activity_for_update`: activity-first FOR UPDATE with
fresh ORM state, under the existing READ COMMITTED transaction. POST checks current
participation, time and quota after taking the lock, then validates the file and
rechecks time. It holds the lock through storage and commit. Concurrent attempts
from two photos produce exactly one success and one 409; attempts from three all
fail. Different users each have their own quota, while activity writes serialize.
The production limit relies on this service path; direct SQL writers must honor
the same lock/quota protocol. SQLite tests do not prove locking.

## External-storage consistency

There is no atomic transaction across S3 and PostgreSQL.

Upload validates permission/quota/file, generates the key, puts the object, inserts
and flushes metadata, rechecks eligibility/time, signs the response and commits.
Any failure before confirmed commit rolls back DB state and attempts an idempotent
object delete, including ambiguous PUT failures. Failed compensation logs the exact
object key for operational cleanup without SDK exception text or credentials, and
preserves the original error. Success requires storage and metadata to succeed.

Deletion verifies activity/photo association, then either active admin privilege
or uploader ownership with normal gallery view access under the activity lock.
It deletes the object first, then metadata and
commits. A storage failure leaves the metadata intact. S3 deletion of a missing
key is successful, so a retry can repair metadata left by a DB failure after object
deletion. Such DB failures are logged with the photo UUID.

Process death between systems, ambiguous DB commit acknowledgements, failed
compensation and failed metadata deletion still need operational reconciliation.
There is no durable outbox, reconciliation worker or retention job.
Migration downgrade drops gallery metadata but cannot delete external objects;
export/reconcile objects before a real rollback. Existing activity/user/membership
rows survive both directions. Test migration cycles use generated temporary DBs.

## S3 / local MinIO

Settings: `S3_ENDPOINT_URL` (omit for AWS), `S3_REGION` (default us-east-1),
`S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, and
`S3_PRESIGNED_URL_TTL_SECONDS` (default 300, allowed 1..900). Credentials use
SecretStr and never enter DTOs. Supply bucket/credentials explicitly; storage
creation is lazy and never blocks API/lifecycle worker startup. Boto3 uses SigV4,
path addressing, bounded connection/read timeouts and two maximum attempts.

Buckets must be private with no public policy/ACL. PUT adds no public ACL and sets
`Cache-Control: private, no-store`. Production provisioning must supply a private
bucket and credentials restricted to the required object operations. No production
bucket is created automatically.

Presigned TTL is the smaller of the configured TTL and remaining gallery seconds,
with a one-second minimum for a still-open subsecond window. S3 signatures have
second granularity, so a URL can remain usable for less than one second after the
application deadline. The API itself always denies at equality. Previously issued
URLs are bearer capabilities until storage expiry; browser-downloaded bytes cannot
be revoked. Reload GET for fresh URLs, never replace them with a permanent URL.

From `backend/`, keep existing local `.env` and add the S3/MinIO entries from
`.env.example`. Do not overwrite an existing environment file:

```powershell
uv sync --frozen
docker compose config --quiet
docker compose up -d --build
docker compose ps
uv run python -m app.scripts.init_photo_storage
uv run alembic upgrade head
uv run fastapi dev app/main.py
```

Compose preserves the PostgreSQL service/volume. MinIO uses its own named volume,
loopback-only S3 port 9000 and console 9001. The [official community project](https://github.com/minio/minio#source-only-distribution)
is source-only and archived; the Dockerfile builds its latest tagged
[security release](https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z),
instead of relying on removed legacy images. This is a local development service.
First build needs network access. Initialization is an explicit repeatable command,
independent of API startup; it creates a missing private bucket and refuses
production mode. The example local credentials must match Compose and S3 settings.
The S3 endpoint must be reachable by both API and browser because it is signed
into the URL; host development uses `http://127.0.0.1:9000`.

## Tests

Default tests require no AWS, MinIO or internet: FakeStorage records writes,
deletes/signatures and injects errors; botocore Stubber checks actual SDK parameters.
`test_gallery.py` covers status permissions, anonymity, exact expiry, cancellation,
quota, formats/corruption/size, safe projections, ordering/query count, ownership
and both storage/DB failure sequences. `test_photo_storage.py` checks private PUT,
idempotent delete, signing, errors, lazy missing configuration and TTL validation.

Set `POSTGRES_TEST_DATABASE_URL` to a migrated disposable PostGIS database and run:

```powershell
uv run pytest -v tests/test_gallery_postgres.py tests/test_gallery_migration_postgres.py
```

These test actual lock waiters, same/different-user quota contention and a clock
advance to exact closure while waiting, without using a sleep as the clock. They
also test cancellation while waiting and the complete temporary migration cycle.
The database role needs CREATEDB/PostGIS permissions for migration tests.

Optional real local storage smoke test (creates/deletes only a random test bucket):

```powershell
$env:MINIO_TEST_ENDPOINT_URL = 'http://127.0.0.1:9000'
$env:MINIO_TEST_ACCESS_KEY_ID = 'do-kompletu-local'
$env:MINIO_TEST_SECRET_ACCESS_KEY = 'do-kompletu-local-only-password'
uv run pytest -v tests/test_gallery_storage_integration.py
Remove-Item Env:MINIO_TEST_ENDPOINT_URL, Env:MINIO_TEST_ACCESS_KEY_ID, Env:MINIO_TEST_SECRET_ACCESS_KEY
```

## Verified frontend contract and remaining integration

Current `ActivityDetailsPage` delegates to `ActivityDetailsContent`, which renders
participant/organizer actions, schedule/windows, location/organizer/tags. It has no
gallery UI or photo placeholders. `activitiesApi.ts` has existing lifecycle API
functions, but no photo API. Both gallery booleans already exist in
`ActivityPermissions`; `ActivityParticipation` already has CHECKED_IN/COMPLETED and
the expiry statuses/timestamps. Backend User/UserRead, frontend UserProfile and
ActivityOrganizer already contain nullable avatar_url; no new avatar persistence
is needed. Organizer rendering uses the existing UserAvatar with fallback.

Existing detail query keys already include user identity and use 60-second
staleness; Axios already handles bearer credentials and refresh. Reuse these
patterns. Older milestone frontend summaries predate these integrations.

Remaining frontend work:

1. Add the DTO above and GET/POST/DELETE functions using the existing API client.
2. Add an identity-scoped gallery query (for example activity-photos/userId/activityId),
   enabled only when authenticated and `can_view_gallery` is true.
3. Add gallery rendering to the detail content with uploader/UserAvatar, empty,
   loading, retry and unavailable states. Render `url` directly in image src;
   never attach the app JWT to the storage URL or persist URLs as stable data.
4. Add an upload control gated by `can_upload_photo`; send FormData with key `file`
   and let the browser set the multipart boundary. Client hints: JPEG/PNG/WebP,
   inclusive 10,485,760 bytes, three own photos. Server validation is authoritative.
5. Show ordinary deletion for `photo.uploader.id === currentUser.id` while gallery
   access remains. Active admins may also delete by known activity/photo IDs,
   including after closure; admin state alone does not enable gallery GET.
   Organizer status alone is insufficient. Handle 204 without parsing JSON.
6. Invalidate the gallery after successful upload/delete, and refresh personalized
   activity/detail/My Activities state after relevant lifecycle changes. Clear
   photo caches on logout/account change using existing auth cache conventions.
7. Refetch for expiring/broken signed URLs while still eligible. Treat 403 from
   the gallery API as loss of access/closure, refresh detail and stop retries;
   object-storage URL expiry alone should prompt a new gallery GET.
8. Handle 401, 403, 404, 409 quota, 413 size, 422 validation, 503 storage and network
   errors with mutation pending/success/failure state; prevent duplicate submissions.
9. Stop access at end_at + 72h (exact equality closed); cancellation keeps eligible
   viewing/deletion but removes upload. Do not derive gallery access from activity
   status alone or interpret activity `can_delete` as photo deletion permission.

The additive photo DTO matches existing public user fields. No current frontend
photo contract conflicts, because none exists. No frontend files were modified.
