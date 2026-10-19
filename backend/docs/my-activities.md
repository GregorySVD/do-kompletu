# My Activities contract

Organizer editing and cancellation are now implemented by the subsequent
[management milestone](activity-management.md). Cancelled rows remain in all
relations and keep the end-time scopes described here; discovery excludes them.
The [participation lifecycle](activity-participation.md) now retains LEFT records
internally; joined lists include current JOINED/CONFIRMED/CHECKED_IN records before
end and also COMPLETED/NO_SHOW in history after explicit
[organizer finalization](activity-finalization.md). LEFT stays excluded.
The [waitlist contract](activity-waitlist.md) adds relation=waitlisted with private
queue-entry time/position, separate from joined membership.
The [check-in contract](activity-check-in.md) describes live counts, timing, proximity,
and checked_in_at privacy; no separate attendance-history endpoint is introduced.
Current combined verification and the migration chain are in the
[root README](../../README.md#testing). Earlier verification below is explicitly historical.

## Current frontend inspection

`frontend/src/pages/MyActivitiesPage/MyActivitiesPage.tsx` is protected by
`RequireAuth` at `/profile/activities`. It uses the auth context for the display name,
but activity data still comes from `mockActivities` and `mockUserActivities`.
The latter has separate `joined_activity_ids` and `organized_activity_ids`; neither
is derived from the authenticated user or current database.

| Question | Inspected behavior |
| --- | --- |
| Mock data | Static activity details, fixed membership/organizer IDs, counts, permissions, and dates; fixtures contain future-feature fields which do not imply those features exist |
| Organized vs joined | Separate ID sets filter the mock array; the organizer section includes all times |
| Time sections | Joined items split using browser time: upcoming `end_at >= now`, history `< now`; ongoing belongs to upcoming |
| Rendered fields | ID/detail link, title, formatted start, category name, venue name, FREE/PAID label, min/max participants, participant count, available slots; missing-to-minimum is derived for presentation |
| Indicators | Section-supplied `Organizujesz` and `Zakończona` labels; no separate joined badge or ongoing section |
| Sorting/pagination | No explicit sorting, tabs, pagination, infinite scroll, or total count; mock array order survives filtering |
| Management | No edit, cancel, or delete controls; cards link to real detail pages, where mock-only UUIDs may return 404 |
| Response convention | Sections accept `Activity[]`; the existing API client and query hooks also use array lists with snake_case fields |

No existing My Activities API function or React Query hook constrains the URL.
The API client sends the sessionStorage access token. Existing query keys lack
user identity, so personalized caches need explicit handling during integration.
The TypeScript detail type still declares `current_user_participation: null`, which
must become a WAITLISTED/JOINED/CONFIRMED/CHECKED_IN/COMPLETED/NO_SHOW object/null union with
nullable joined_at, waitlisted_at, waitlist_position, effective_confirmation_deadline_at,
confirmation_expired_at/waitlist_expired_at, and attendance timestamps. Add
CONFIRMATION_EXPIRED/WAITLIST_EXPIRED to the union for private detail. Poll/refetch
detail and personal lists during pre-start windows to observe autonomous changes.
Add can_finalize alongside can_cancel/cancelled_at. Existing checkin_* metadata and can_check_in
types/panel can be reused; browser geolocation and actions still need integration.
The existing confirmation_opens_at/confirmation_deadline_at and can_confirm fields
now carry real backend behavior; API functions, mutation hooks, and UI are still absent.

## API design

`GET /api/v1/users/me/activities` requires an access JWT. There is one endpoint,
with relation and time filtering rather than duplicated routes. No client user ID
is accepted: unknown fields, including `user_id`, return 422. Identity comes from
the access token and normal active-user checks apply.

| Field | Contract |
| --- | --- |
| `relation` | Required, case-sensitive `organized`, `joined`, or `waitlisted` |
| `scope` | Optional, case-sensitive `upcoming` or `history`; omit for all times |
| `limit` | Integer, default 20, inclusive range 1-100 |
| `offset` | Integer, default 0, minimum 0 |

There is no `relation=all`, `scope=all`, separate ongoing filter, arbitrary sort,
or speculative discovery filter on this endpoint. The optional scope preserves
the frontend's existing all-organized section without merging the relations.

| Frontend section | Request query |
| --- | --- |
| Nadchodzące | `relation=joined&scope=upcoming` |
| Waitlist | `relation=waitlisted&scope=upcoming` |
| Organizowane przeze mnie | `relation=organized` (omit scope) |
| Historia | `relation=joined&scope=history` |

Organized selects `organizer_id == current_user.id`. Joined selects persisted
JOINED/CONFIRMED/CHECKED_IN membership for the caller before end. At/after end it
also selects COMPLETED/NO_SHOW outcomes. LEFT and the caller's organized activities
are always excluded. Leaving an uncancelled activity before end marks its row
LEFT and removes the item from joined lists without deleting the record. Eligible
rejoin reactivates the row. Ended/cancelled active memberships remain listed;
cancellation blocks all participation actions. CHECKED_IN cannot leave even before
end. A separate list of left activities
is not implemented, including in history scope.
Waitlisted selects only the caller's WAITLISTED rows and excludes organizer-owned
activities. It preserves cancelled rows and uses the same end-time scopes, so
upcoming can include ongoing waitlisted events until a sweep expires the queue.
The [lifecycle worker](participation-lifecycle-worker.md) expires overdue JOINED
and remaining WAITLISTED at start. CONFIRMATION_EXPIRED is excluded from joined;
WAITLIST_EXPIRED is excluded from waitlisted. Both remain caller-only on direct
detail, without a new section. Cancelled records are skipped by automation and
retain their original evidence. WAITLISTED never appears in joined relation,
never consumes participant capacity, and never becomes NO_SHOW/COMPLETED.
No other user's membership is returned.

A single timezone-aware UTC cutoff is captured after authentication and used for
filtering and serialization of the entire page:

- Upcoming: `end_at > cutoff`, including ongoing; sort `start_at ASC, id ASC`.
- History: `end_at <= cutoff`; sort `end_at DESC, id ASC`.
- Scope omitted: upcoming/ongoing first by start ascending, then history by end
  descending; ID ascending breaks ties in each group.

The exact end instant is history, matching existing ENDED status and participation
rules. This intentionally tightens the frontend mock split's `>=`/`<` boundary.
The client should use server-filtered lists rather than classify them again using
its own clock.

Pagination applies after relation/scope filters and sorting. The result is a JSON
array of existing `ActivityRead` objects, a superset of card fields that also carries
membership and permissions. Reusing it avoids another near-identical response DTO.
No total count, page wrapper, or `has_more` is introduced because current frontend
list conventions do not need one. Continue until a short or empty page; a full
final page may require one extra empty fetch. Different requests use fresh cutoffs
and database snapshots, so concurrent changes or activity endings can shift offsets.

## Exact response example

```http
GET /api/v1/users/me/activities?relation=joined&scope=upcoming&limit=20&offset=0
Authorization: Bearer <access_token>
```

200 OK, `Content-Type: application/json`, `Cache-Control: private, no-store`,
`Vary: Authorization`:

```json
[
  {
    "id": "d54112d9-43cf-4986-8679-b6c236ac522c",
    "title": "Siatkówka na Orliku",
    "category": {
      "id": "623c6216-f59e-4167-a238-bfda04d99488",
      "name": "Sport zespołowy",
      "slug": "sport-zespolowy"
    },
    "start_at": "2030-08-08T16:00:00Z",
    "end_at": "2030-08-08T18:00:00Z",
    "location_name": "Orlik przy ul. Gdańskiej",
    "address": "ul. Gdańska 1, Poznań",
    "latitude": 52.4232,
    "longitude": 16.9461,
    "distance_m": null,
    "price_type": "FREE",
    "min_participants": 4,
    "max_participants": 12,
    "participant_count": 1,
    "checked_in_count": 0,
    "waitlist_count": 0,
    "available_slots": 11,
    "status": "PUBLISHED",
    "cancelled_at": null,
    "description": "Amatorski mecz siatkówki dla każdego chętnego.",
    "organizer": {
      "id": "bb1aedb3-54f4-45c4-ab10-2fb0a07b53ca",
      "display_name": "Organizer",
      "avatar_url": null
    },
    "tags": [],
    "confirmation_opens_at": "2030-08-08T15:00:00Z",
    "confirmation_deadline_at": "2030-08-08T15:30:00Z",
    "checkin_opens_at": "2030-08-08T15:30:00Z",
    "checkin_closes_at": "2030-08-08T17:00:00Z",
    "checkin_radius_m": 150,
    "price_amount": null,
    "currency": null,
    "current_user_participation": {
      "status": "JOINED",
      "joined_at": "2030-08-01T12:00:00Z",
      "confirmed_at": null,
      "checked_in_at": null,
      "completed_at": null,
      "no_show_at": null
    },
    "permissions": {
      "can_edit": false,
      "can_cancel": false,
      "can_finalize": false,
      "can_delete": false,
      "can_join": false,
      "can_leave": true,
      "can_confirm": false,
      "can_check_in": false,
      "can_view_gallery": false,
      "can_upload_photo": false
    }
  }
]
```

Example IDs/timestamps are illustrative. Swagger also includes complete selectable
organized, joined-history, and empty-array examples. Organized responses use the
same schema with normally null membership and organizer can_edit/can_cancel/can_finalize
based on lifecycle; history keeps unresolved JOINED/CONFIRMED/CHECKED_IN plus final
COMPLETED/NO_SHOW, with all participant actions disabled. Final outcomes never
appear in upcoming. Cancelled
activities retain membership with all permissions false. Unlimited capacity returns null for both
`max_participants` and `available_slots`. Participant counts exclude the organizer;
participant_count remains the active capacity count and becomes zero after finalization.
checked_in_count counts CHECKED_IN + COMPLETED and waitlist_count counts WAITLISTED only.
Current participation includes nullable confirmed_at/checked_in_at/completed_at/no_show_at
belonging only to the caller, including final outcomes in direct detail/history.
LEFT returns null current participation. Public confirmation timing is derived in
ActivityRead, with can_confirm true only for eligible JOINED users in the window.

No matches or an offset beyond the result set returns exactly:

```json
[]
```

| Status | Example/error meaning |
| --- | --- |
| 401 | Missing token: `{"detail":"Not authenticated"}` |
| 401 | Invalid/expired/refresh token or unavailable user: `{"detail":"Could not validate credentials"}` |
| 422 | Standard FastAPI validation detail list for missing/invalid filters, pagination, or unknown query fields |

## Query strategy and migrations

`list_user_activities` builds one parameterized SQL statement with organizer
eager-loading, indexed organizer equality or membership EXISTS filtering, and
limit/offset. Existing shared projections add correlated count and caller timestamp
subqueries plus PostGIS coordinate extraction. The membership primary key covers
activity/user lookups; the user index supports user-scoped membership discovery.
The organizer index already exists. Database subqueries perform indexed work inside
one statement; they do not issue separate client/server queries per item.

The SQL request count is constant: one user lookup for authentication and one
activity SELECT. Public `GET /activities` was already a one-statement projection;
its contract and query count remain unchanged. Public list serialization now also
uses one captured cutoff, with its active-first boundary aligned to ENDED semantics.
This is a round-trip guarantee, not a claim that database CPU work is independent
of page size. No formal benchmark or additional index is justified for this milestone.

The My Activities milestone needed no migration or schema change. Its historical
migration-file/database head was `20261018_0004`, using `localhost:5433`.
The subsequent management migration adds cancelled_at, and lifecycle migration
`20261018_0006` adds status/left_at/confirmed_at; 0007 adds checked_in_at and CHECKED_IN.
Migration 0008 adds COMPLETED/NO_SHOW and completed_at/no_show_at.
Current head is `20261019_0010`; see the waitlist contract for nullable joined_at,
waitlisted_at, FIFO index, unchanged-data upgrade, and lossy inactive-LEFT downgrade.
The relation/scope query contract is unchanged; membership predicates/projections
now distinguish upcoming current states from current/final history states in SQL.

## Tests and integration work

Isolated tests cover authentication/active-user checks, JWT scoping, relation/time
filters, exact end/start boundaries and microseconds, stable ordering, pagination,
invalid parameters, full/unlimited counts, caller state/permissions, empty pages,
join/leave visibility, offset normalization, shared-cutoff consistency, and query
counts. The OpenAPI test checks required authentication, query parameters, array
schema, and complete examples including nulls.

PostgreSQL integration tests separately exercise real timestamptz behavior with
non-UTC inputs and positive/negative connection time zones, UUID tie ordering,
scope/pagination, PostGIS coordinates, counts/state, and constant SELECT counts.
Their fixtures use an outer transaction with savepoints and roll back all test
records. SQLite does not prove these PostgreSQL properties. Existing auth,
participation locking, categories, public activity APIs, and bootstrap regressions
remain covered by their existing suites.

### Historical My Activities milestone verification

These results predate organizer management. For current combined test counts and
the current migration head, see [the README](../../README.md#testing).

| Check | Result |
| --- | --- |
| `uv run pytest -v` | 164 passed; 20 environment-gated PostgreSQL tests skipped |
| Separate PostgreSQL run across all three integration modules | 20 passed, including nine new My Activities cases and existing concurrency tests |
| `uv run ruff check .` | Passed |
| `uv run python -m compileall app` | Passed |
| `uv lock --check` | Passed; lockfile unchanged |
| `uv run alembic current` | `20261018_0004`, the head at that milestone; no listing-specific migration |
| Documentation JSON | Parsed and matched to the API examples exactly |
| Database cleanup | One existing user, zero activities, zero memberships after tests |
| `git diff --check` | Passed |
| Frontend diff | Empty |

56 test cases were added: 46 isolated, nine PostgreSQL, and one OpenAPI contract
test. The runs retain the existing Starlette TestClient/httpx deprecation and a
local pytest-cache permission warning; neither was suppressed. Git also reports
the existing root cache-directory permission warning and LF/CRLF notices.
Work stayed on `backend`, without commits, pushes, merges, or development-data removal.

Frontend work still required:

1. Add a My Activities API function and authenticated query hook with user ID,
   relation, scope, limit, and offset in the query key. The user ID is a cache key
   component only and must not be sent as an API parameter.
2. Replace the three mock-derived arrays with the section requests above; remove
   browser-clock classification and keep section labels/empty states.
3. Add loading, retry/error, and pagination/load-more handling. Fetch after auth
   restoration and handle token refresh/re-authentication on 401.
4. Update the membership TypeScript union/timestamps including COMPLETED/NO_SHOW
   and completed_at/no_show_at; add cancelled_at/can_cancel/can_finalize.
   Add confirmation API/hooks/UI using existing timing/can_confirm fields. Invalidate
   personal lists after create, join, leave, confirm, check-in, edit, cancel, and finalize, and clear/remove them
   on logout/account changes.
5. Add edit/cancel actions using can_edit/can_cancel and the management endpoints;
   display CANCELLED/cancelled_at while retaining membership context.
6. Render the caller's COMPLETED/NO_SHOW outcome separately from Activity ENDED;
   add organizer finalize action/result/error handling using can_finalize. Existing
   fixtures have no attendance-outcome UI. Future review/XP eligibility may use
   COMPLETED only after those product features and policies are implemented.

No edit/cancel/delete controls currently exist in the frontend. The new
[management contract](activity-management.md) supplies organizer editing/cancellation;
hard deletion remains unimplemented. Timed attendance confirmation is implemented
by the participation contract, with PostGIS check-in described separately.
Explicit finalization implements final attendance; it does not run automatically.
Reviews, XP, rewards, ranks, achievements, chat,
notifications, and gallery features remain outside this milestone.
