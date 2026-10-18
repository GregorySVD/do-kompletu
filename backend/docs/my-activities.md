# My Activities contract

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
must become `{ status: 'JOINED'; joined_at: string } | null`.

## API design

`GET /api/v1/users/me/activities` requires an access JWT. There is one endpoint,
with relation and time filtering rather than duplicated routes. No client user ID
is accepted: unknown fields, including `user_id`, return 422. Identity comes from
the access token and normal active-user checks apply.

| Field | Contract |
| --- | --- |
| `relation` | Required, case-sensitive `organized` or `joined` |
| `scope` | Optional, case-sensitive `upcoming` or `history`; omit for all times |
| `limit` | Integer, default 20, inclusive range 1-100 |
| `offset` | Integer, default 0, minimum 0 |

There is no `relation=all`, `scope=all`, separate ongoing filter, arbitrary sort,
or speculative discovery filter on this endpoint. The optional scope preserves
the frontend's existing all-organized section without merging the two relations.

| Frontend section | Request query |
| --- | --- |
| Nadchodzące | `relation=joined&scope=upcoming` |
| Organizowane przeze mnie | `relation=organized` (omit scope) |
| Historia | `relation=joined&scope=history` |

Organized selects `organizer_id == current_user.id`. Joined selects persisted
membership for the caller and excludes the caller's organized activities.
Leaving removes an item from joined lists; ended memberships remain in history.
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
    "description": "Amatorski mecz siatkówki dla każdego chętnego.",
    "organizer": {
      "id": "bb1aedb3-54f4-45c4-ab10-2fb0a07b53ca",
      "display_name": "Organizer",
      "avatar_url": null
    },
    "tags": [],
    "confirmation_opens_at": null,
    "confirmation_deadline_at": null,
    "checkin_opens_at": null,
    "checkin_closes_at": null,
    "checkin_radius_m": null,
    "price_amount": null,
    "currency": null,
    "current_user_participation": {
      "status": "JOINED",
      "joined_at": "2030-08-01T12:00:00Z"
    },
    "permissions": {
      "can_edit": false,
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
same schema with normally null membership and all permissions false; history keeps
JOINED membership but disables leaving. Unlimited capacity returns null for both
`max_participants` and `available_slots`. Participant counts exclude the organizer;
checked-in and waitlist counts stay zero.

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

No migration or schema change was needed. Both migration-file head and the real
development database were verified as `20261018_0004`, using `localhost:5433`.

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

Final verification for this milestone:

| Check | Result |
| --- | --- |
| `uv run pytest -v` | 164 passed; 20 environment-gated PostgreSQL tests skipped |
| Separate PostgreSQL run across all three integration modules | 20 passed, including nine new My Activities cases and existing concurrency tests |
| `uv run ruff check .` | Passed |
| `uv run python -m compileall app` | Passed |
| `uv lock --check` | Passed; lockfile unchanged |
| `uv run alembic current` | `20261018_0004 (head)`; no new migration |
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
4. Update the membership TypeScript union. Invalidate personal lists after create,
   join, and leave, and clear/remove them on logout/account changes.
5. Keep management actions disabled until organizer editing/cancellation APIs exist.

No edit/cancel/delete controls currently require a contract. The recommended next
backend milestone is organizer editing and cancellation, with ownership checks and
the existing activity lock protecting lifecycle and capacity changes. A cancellation
contract must define joined-user/history behavior before implementation.
Waitlist, confirmation, check-in, reviews, XP, rewards, ranks, achievements, chat,
notifications, and gallery features remain outside this milestone.
