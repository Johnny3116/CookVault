# Changelog

All notable changes to CookVault are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Nothing is git-tagged yet, so **Unreleased** is everything not on `main`, and
dates are commit dates rather than release dates.

## [Unreleased]

### Added

- Unit normalization layer (`backend/app/units.py`), the thing spec §7 flags as
  the trap to solve early: alias resolution, exact Decimal conversion within a
  dimension, and merge rules that refuse to invent numbers. Mass and volume
  deliberately never combine, since that needs a density.
- Shopping list generation now merges duplicate ingredients across recipes,
  summing compatible units and reporting the total in the unit the recipe was
  written in. Incompatible amounts stay as separate lines.
- Generating a shopping list is idempotent: it replaces what the last generate
  produced and leaves hand-added items alone. It previously appended, so a
  second press silently doubled the list.
- `DELETE /shopping-list`, with `?checked_only=true` to clear just the ticked
  items, and a shopping list UI that can generate from selected recipes, delete
  single items, and set quantity, unit and category when adding by hand.
- Library filtering by tag, cook method, total time and title search, combinable
  and held in the URL so a filtered view is shareable. `GET /recipes/facets`
  reports the tags and cook methods actually in use, so the filters offer real
  choices instead of a free-text guess.
- Calendar week navigation (previous, next, back to this week), with today's
  column highlighted.
- GitHub Actions CI (`.github/workflows/ci.yml`) running on every pull request
  and every push to `main`: the backend job applies the migrations, reverses
  them to base and reapplies them, runs `alembic check` for model drift and
  runs the test suite against a real Postgres service container; the frontend
  job typechecks and builds; a third job builds both Docker images, since a
  Dockerfile that no longer builds is a broken deploy even when the app code
  is fine.
- Backend test suite (`backend/tests/`, 32 tests) covering recipe CRUD,
  ingredient ordering, `PUT` replacement, partial `PATCH` on children, the
  password gate, shopping lists, meal planning and the Phase 2 stubs. Each
  test that exists for a previously-fixed bug was checked by reintroducing
  that bug and confirming the test goes red.
- Recipes can be edited, deleted and favorited from the UI. Previously the
  frontend could only create and read, so correcting a typo meant reaching for
  `curl`.
- `PUT /recipes/{id}`, which replaces a recipe and all of its children in one
  call, so the edit form doesn't have to diff ingredients and steps against the
  per-child endpoints.
- Login page and a 401 redirect, making the optional `COOKVAULT_PASSWORD` gate
  usable for the first time.
- `POST /auth/logout`, and `PATCH /recipes/{id}/alternates/{alternate_id}` to
  complete the alternates CRUD surface.
- Tags, cook methods, estimated cost, source URL, favorite and alternates on the
  recipe form. Without tags and favorite there was no way to produce the data
  the library's filters read.
- Step reordering controls in the recipe form.
- `position` column on ingredients, with migration `0002` backfilling existing
  rows by name, plus a `(recipe_id, position)` index.
- Backend entrypoint that runs `alembic upgrade head` on startup, and a Postgres
  healthcheck that Compose waits on before starting the backend.
- `.dockerignore` for both images.
- Shared date helpers (`frontend/lib/dates.ts`) and quantity/cost formatting
  helpers (`frontend/lib/format.ts`).

### Changed

- `GET /recipes` takes `tag` where it previously took `cuisine`; the parameter
  filtered on tags either way, and the old name described something the data
  model doesn't have.
- **The browser now only talks to one origin.** `/api/*` is proxied server-side
  to the backend by `frontend/app/api/[...path]/route.ts`. This removes the CORS
  configuration, takes the backend address out of the client bundle, makes the
  session cookie same-origin, and leaves a single port to front with
  `tailscale serve`.
- The proxy is a route handler rather than a Next `rewrites()` entry, because
  rewrite destinations are resolved at *build* time and baked into the routes
  manifest — an environment variable cannot repoint one at deploy time.
- The session cookie holds an HMAC-signed, 30-day token instead of the password
  itself.
- CORS middleware is only mounted when `CORS_ORIGINS` is explicitly set; it is
  empty by default and no longer needed in normal operation.
- Frontend image builds with `npm ci` against a committed lockfile instead of
  `npm install` against a glob that matched nothing.
- `BACKEND_ORIGIN` (server-side, runtime) replaces `COOKVAULT_PUBLIC_API_URL` /
  `NEXT_PUBLIC_API_URL` (client-side, baked in at build time). Changing the
  address the app is served on no longer requires a rebuild.
- Dashboard shows the actual planned meals rather than a count of them.
- Recipe detail page shows tags, cook methods and source link, and labels each
  alternate by kind.

### Fixed

- Setting `COOKVAULT_PASSWORD` bricked the app. There was no login page, the
  client never sent credentials, and the `samesite=lax` cookie without `secure`
  could not have survived the cross-origin hop regardless.
- Ingredients were ordered by their random UUID primary key, so the four-column
  layout rendered them in arbitrary order and reshuffled after every edit.
- The dashboard's week window was off by one all evening west of UTC: it called
  `toISOString()` on a `Date` still carrying a local time-of-day, so the day
  rolled forward. The calendar was already correct; both now share one helper.
- `PATCH` on ingredients and steps took schemas whose fields were required, so
  a partial update was impossible — a PUT in a PATCH's costume.
- Quantities rendered as `1.500 cup flour`. The API serializes `NUMERIC` as a
  JSON string, which the TypeScript types incorrectly declared as `number`.
- The backend raced Postgres on first boot and relied on `restart: unless-stopped`
  to recover.
- Image builds were not reproducible: no lockfile was committed, so every build
  re-resolved dependencies from scratch.
- `COPY . .` pulled the host's `node_modules`/`.next` (and the backend's
  `__pycache__`/`.venv`) into the build context, clobbering the install step.
- The `(recipe_id, position)` index existed in the migration but not on the
  model, so `alembic` autogenerate would have proposed dropping it.

### Security

- The session cookie no longer contains the password in plaintext. Cookies
  minted under the old scheme are rejected.
- Login compares passwords with `hmac.compare_digest` rather than `!=`.

## [0.1.0] - 2026-09-10

Initial scaffold — everything currently on `main`.

### Added

- FastAPI backend with SQLAlchemy models and Alembic migration `0001` covering
  recipes, ingredients, steps, alternates, shopping list items and meal plan
  entries.
- REST endpoints for recipes and their children, shopping lists and meal
  planning; `501 Not Implemented` stubs for the Phase 2 features (link import,
  LLM-backed finder, auto-fill planning) rather than faked behavior.
- Next.js frontend: dashboard, recipe library, four-column recipe detail page,
  manual entry form, recipe finder, shopping list and weekly calendar.
- Docker Compose stack with Postgres, with every host port bound to `127.0.0.1`
  for Tailscale-only deployment and Postgres not exposed to the host at all.
