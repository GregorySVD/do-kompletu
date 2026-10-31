# Minimal administration and moderation

The backend MVP uses a simple `User.is_admin` boolean, not a general role system.
There are no role/permission tables, moderator tiers or self-service privilege
changes. The backend enters **FEATURE FREEZE** after this milestone.

## Accounts and authorization

Migration `20261031_0012`, following `20261030_0011`, adds
`users.is_admin BOOLEAN NOT NULL DEFAULT false`. Existing accounts become ordinary
users. The false server default remains for safe ORM and direct SQL inserts;
the ORM also defaults to false. No account is automatically promoted.

Admins log in through the existing JSON login or Swagger token form and use the
ordinary access bearer token. `require_admin` reuses `get_current_user`, which
resolves the JWT subject to the current database user and rejects absent/inactive
accounts. Missing/invalid/expired/wrong-type JWTs and inactive users return 401;
an active non-admin returns 403. Admin state is read from the database, never from
an `is_admin` JWT claim. Removing admin status takes effect on subsequent requests.

`GET /api/v1/users/me` includes `is_admin`. Registration and profile-update responses
also use the same own-account `UserRead`. Public organizer and photo-uploader
projections remain only `id`, `display_name`, `avatar_url`; they never gain email,
admin state, password hashes or private participation evidence. Normal register
and profile request schemas do not have `is_admin`: their existing unknown-field
ignore behavior is preserved, so a supplied privilege field cannot change it.

## Four administration endpoints

All are under `/api/v1/admin`, tagged **Administration**, and require an active
admin. Successful responses use `Cache-Control: private, no-store` and
`Vary: Authorization`.

| Method/path | Behavior and response |
| --- | --- |
| GET `/users` | Array of `AdminUserRead`: id, email, display_name, is_active, is_admin, points_total, created_at. Includes inactive users. |
| PATCH `/users/{user_id}/active` | Body `{"is_active": false}` or `{"is_active": true}`; returns updated `AdminUserRead`. |
| GET `/activities` | Array of `AdminActivityRead`, including ongoing, future, ended and cancelled records. |
| POST `/activities/{activity_id}/cancel` | No request body; returns the cancelled `AdminActivityRead`. |

Both lists accept `limit` (default 20, 1..100) and `offset` (default 0, >=0).
Ordering is `created_at ASC, id ASC`; both fields determine stable ordering before
pagination. Responses are plain arrays, without a total-count wrapper or a
cross-page snapshot guarantee.

`AdminActivityRead` contains id, title, safe organizer, derived status, start_at,
end_at, cancelled_at, participant_count, waitlist_count and created_at. Counts use
the existing shared SQL projections. It contains no participant list, emails,
participation timestamps, gallery URLs/keys, or caller-specific permissions.

Activation accepts only the required JSON boolean `is_active`; strings, numbers,
null, missing/unknown fields (including `is_admin`) return 422. Unknown users
return 404. Self-deactivation returns 409 with
`Administrators cannot deactivate themselves`. Repeating another account's
requested state succeeds; self-activation is harmless and allowed.

After deactivation, login, protected requests with an already-issued access JWT,
and refresh with an already-issued refresh JWT all return 401 through existing
central authentication. No blacklist or cryptographic revocation is introduced.
Reactivation restores authentication, including still-valid pre-existing tokens.
Already-authorized in-flight requests are not forcibly interrupted. Deactivation
does not cancel organized activities, erase attendance, change points or remove
stored photos. An admin may deactivate another admin; no last-admin policy exists.

## Cancellation and domain invariants

The admin route calls the same `activity_management_service.cancel_activity`
used by the organizer. Only its trusted ownership authorization differs. The
ordinary organizer endpoint still enforces ownership, even for an unrelated admin.
Both routes acquire the same activity-first `SELECT FOR UPDATE`, refresh cached
state, check domain rules after waiting, set cancelled_at, build the response
snapshot and commit; failures roll back.

An already-cancelled activity returns 409 without changing its timestamp. An
ended activity, including exact end_at, returns 409. Unknown IDs return 404.
Cancellation is soft: discovery omits it, direct detail and personal history
retain it, participation/check-in evidence and existing photos remain. Further
participation mutations, finalization and photo uploads stay blocked. Normal
eligible gallery viewing and own-photo deletion remain available until closure.
There is no direct status mutation, ownership impersonation or hard-delete API.

## Photo moderation and the 72-hour boundary

Use the existing DELETE
`/api/v1/activities/{activity_id}/photos/{photo_id}`. An active admin may delete any
existing photo using these IDs without being organizer/participant or having
gallery-view permission. This includes the exact `end_at + 72h` boundary and later.
Activity and photo existence/association are still checked; missing or mismatched
IDs return 404. Success is 204 with no body or storage details.

For ordinary users, only the uploader may delete while normal gallery-view access
remains. Organizer identity alone does not permit deleting another user's photo.
Admin status does not grant normal gallery GET or upload rights. ActivityRead
gallery permissions continue to describe normal browsing/upload eligibility.
There is no additional admin photo list, photo-read or photo-delete endpoint.
Photo IDs must therefore come from an existing authorized gallery response or
trusted local moderation tooling/report; this milestone has no reporting workflow.

The existing activity lock and storage-first strategy apply equally to admins:
delete the object, then remove metadata and commit. A storage error returns safe
503 `Photo storage unavailable` and preserves DB metadata. A missing storage
object is an idempotent success. If DB commit fails after object removal, rollback
retains metadata; retry removes the metadata even though the object is already
absent. There is no atomic S3/PostgreSQL transaction, durable reconciliation job,
retention cleanup or audit log.

## Local admin provisioning and migration

The existing bootstrap script still creates an ordinary account, is disabled in
production and never promotes users. No public make-admin endpoint exists.
After normal registration/bootstrap and `uv run alembic upgrade head`, use trusted
local SQL against the intended development database. Replace the placeholder
with the exact UUID from your own `/users/me` response:

```sql
BEGIN;
UPDATE users
SET is_admin = true
WHERE id = '<chosen-user-uuid>'::uuid AND is_active = true
RETURNING id, display_name, is_active, is_admin;
-- Verify exactly the intended account was returned before committing.
COMMIT;
```

Use `ROLLBACK` instead of `COMMIT` if the returned account is wrong. Setting
is_admin=false through the same trusted tooling removes the privilege on future
requests. No administrator was provisioned as part of automated validation.

The migration cycle `0011 -> 0012 -> 0011 -> 0012` is tested on a generated
temporary PostgreSQL/PostGIS database. Upgrade preserves users, activities,
participations and gallery metadata and defaults existing users to false.
Downgrade drops only is_admin; it loses admin assignments. Re-upgrade defaults
all existing users to false again. Never run the test downgrade on development
or production data merely to verify a migration.

## Frontend integration remaining

Current frontend already has real My Activities, participant actions (including
geolocation check-in), organizer editing/cancellation/finalization, profile editing,
access-token refresh and identity-scoped private queries. Those remain unchanged.

1. Add `is_admin: boolean` to `frontend/src/types/auth.ts` `UserProfile`; source it
   from `/users/me` through the existing AuthContext, never from decoded JWT claims.
2. Add admin navigation/routes in `frontend/src/App.tsx` and a guard alongside
   `RequireAuth`. Handle loading, unauthenticated and non-admin states; continue
   handling backend 401/403 when a stale profile loses access.
3. Add typed admin API functions, limit/offset queries and per-admin cache keys.
   Include admin queries in `clearPrivateClientState` in AuthContext.
4. Build a paginated user moderation table with email, balance, account/admin
   state, active toggle, pending/error feedback and disabled self-deactivation.
   Invalidate affected lists/profile after activation changes; do not add privilege
   editing. Existing 401/refresh rejection already expires a deactivated session.
5. Build the activity moderation list with lifecycle/counts and a cancel action
   using the admin route. Invalidate admin lists, detail, discovery and relevant
   personal queries. Ordinary organizer cancellation remains a separate client action.
6. Add a photo moderation action using activity/photo IDs and the existing DELETE
   path, with confirmation, 204/404/503 handling and retries. There is no current
   gallery client/UI and no admin browsing grant; do not assume GET works for
   an unrelated admin or after closure. A minimal UI can accept known IDs.

The normal app continues to work without an admin UI. No frontend files changed.
No additional MVP backend features are proposed: richer moderation, audit logs,
RBAC and the other deferred product features are outside the frozen MVP.
