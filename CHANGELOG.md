# Changelog

All notable changes to CookVault are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Nothing is git-tagged yet, so **Unreleased** is everything not on `main`, and
dates are commit dates rather than release dates.

## [Unreleased]

### Added

- **The `/agent` tool surface** — the door Agent Zero comes in through.
  CookVault is the server, not the client, which is what made this buildable:
  an agent calling *in* needs no guess about anyone else's wire format, and
  every write it can attempt is one CookVault wrote and validates. Read tools
  (`parse_recipe_source`, `search_recipes`, `get_recipe`, `suggest_meal_plan`)
  and propose tools (`create_recipe_draft`, `update_recipe_draft`,
  `create_meal_plan_draft`). Every write creates a draft; nothing on this
  surface writes a recipe, a meal plan entry, a shopping list or a backup, and
  promotion and approval are not on it at all. The route list is pinned as a
  literal in the tests, and `GET /agent/manifest` is asserted to describe
  exactly what is mounted.
- **A separate door for it.** `AGENT_API_KEY` and an `X-API-Key` header,
  unrelated to the password gate in both directions: a cookie does not open
  `/agent`, and the agent key does not open John's endpoints. Unset means the
  surface answers 503 rather than coming up open; a key under 32 characters
  refuses to boot.
- **Draft authorship and notes** (migration `0009`). `created_by` is a fact
  about which door a draft came through rather than something inferred from
  provenance, which is what makes "the agent cannot edit a draft John started"
  enforceable. `note` is what the proposer wanted to say to the reviewer, and
  never becomes part of the recipe.
- **Auto-fill meal planning** (migration `0010`), which needed no model at all.
  "Diverse" is arithmetic over the cook log, so `POST /meal-plan/auto-fill`
  proposes a week itself and shows its working — every meal carries the
  sentence that put it there. The result is a `meal_plan_draft`: the calendar
  is untouched until you approve it at `/calendar/proposals`, where any meal
  can be swapped or dropped first.
- **`services/recipe_search.py`**, one query shared by the library page and the
  agent's search tool, so the two cannot drift apart.
- A test that the backup covers every mapped table — the one part of that
  feature that could not fail loudly.

- **Shopping aisles** (migration `0006`), a different axis from ingredient
  category: category is what a thing is when you cook with it, aisle is where
  you walk to pick it up. The mapping is rows in `aisle_rules`, seeded with 161
  terms and editable at runtime. Longest match wins, whole-word only, no match
  is `other`. An item's aisle is resolved per response so fixing a rule fixes
  every line; `aisle_override` is there when you know better.
  `GET /aisles/resolve` names the rule that decided. The shopping list is
  grouped by aisle and reads as a route through a shop.
- **Cooking history** (migration `0007`). `cook_log` records what was actually
  made and when, with a rating and note per occasion. `times_cooked` and
  `last_cooked_on` are derived from the log rather than counted on the recipe.
  `GET /history` is a recent feed; the library gains "Not made in ages" and
  "Made most often".
- **Pantry** (migration `0008`): names and notes, no quantities and no expiry
  dates. It flags a shopping line as something you probably already have and
  never removes one.
- **Backup and restore.** `GET /backup/export` dumps the whole library as JSON
  with ids preserved; `POST /backup/restore` replaces everything in one
  transaction, requires `confirm: "replace"`, and refuses an unrecognised
  format version. A round-trip test builds a library with a row in every table,
  wipes it, restores and compares the whole export for equality.

- `httpx` is now a runtime dependency, not just a test one: URL import needs an
  HTTP client.
- **Import into a draft.** `POST /import` takes a URL, `POST /import/paste`
  takes text, and both create a draft — never a recipe, with no flag to skip
  the review. `POST /import` previously returned `501`.
- URL import reads the page's `schema.org/Recipe` JSON-LD when it is there, so
  the amounts are the ones the publisher typed rather than something inferred,
  and falls back to the text heuristic when it is not.
- `backend/app/services/recipe_text.py` parses written recipes: mixed and
  vulgar fractions ("1 1/2", "½", "1½"), glued amounts ("400g"), ranges (lower
  bound), `Ingredients:`/`Method:` headings when present, and a first guess at
  the four ingredient columns. Step numbers are assigned by position, so a
  parsed draft cannot trip validation's sequence check.
- `backend/app/services/web_import.py` fetches pages and refuses to fetch
  anything that is not a public http(s) address — loopback, private,
  link-local, reserved and multicast hosts are rejected after DNS resolution,
  so a pasted link can't make CookVault read something inside the network.
- An import page in the UI (URL or paste), reachable from the drafts queue.
- **Recipe drafts** (migration `0005`). A staging area in front of the
  cookbook: `POST /drafts` to propose, `PATCH` to edit, `/validate` to check,
  `/promote` to turn into a real recipe, `/discard` to reject. Promotion is the
  only route from a draft into `recipes`. Built and proven by hand now so that
  an agent, when it is eventually allowed to propose recipes, gets the same
  door and no other.
- Draft validation (`backend/app/services/drafts.py`) reports two severities.
  Errors block promotion — nothing parseable, no ingredients, no steps, step
  numbers that aren't a 1..n sequence, negative times. Warnings don't — a unit
  the app can't convert, an ingredient listed twice — because both are
  legitimate things to write and also the classic shapes of a bad extraction.
- Editing a draft's payload drops its status from `ready` back to `draft`, and
  promotion revalidates rather than trusting the stored status.
- **Recipe provenance** (migration `0005`): `source_type`, `source_url`,
  `source_title`, `import_method`, `imported_at`, `agent_model`,
  `agent_version`, plus `original_text` and `extracted_payload` stored
  separately so the raw source can still be compared against what was extracted
  from it. One row serves a draft and the recipe it is promoted into; it is
  shown on both, and on `GET /recipes/{id}`.
- A drafts UI: the review queue filtered by status, a new-draft page that
  records where the content came from, and a draft page that validates, shows
  the issues, and promotes.
- Recipe scaling. `GET /recipes/{id}?servings=N` returns the recipe scaled to a
  target, leaving the stored recipe canonical; the response reports the scale
  applied. A recipe with no recorded yield comes back unchanged rather than
  being scaled from a guessed baseline.
- Meal plan entries carry planned servings and a meal slot (migration `0004`).
  Servings are stored as a target rather than a multiplier, so they stay
  meaningful if the recipe's own yield is later corrected.
- `POST /shopping-list/generate` accepts a `start`/`end` span and buys the
  servings actually planned for each day, scaling each recipe from its own
  yield before normalizing and merging. Spans and ad-hoc `recipe_ids` combine
  in one call.
- `PATCH /meal-plan/{id}` to move an entry or change its servings or meal slot.
- `backend/app/services/` — the domain layer shared by recipe scaling and
  shopping-list generation, extracted at the point a second real caller
  appeared rather than in advance.
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

- `POST /meal-plan/auto-fill` proposes a week instead of returning `501`, and
  `POST /meal-plan` with `mode: "auto"` is now a `400` pointing at it rather
  than a `501`. Approving a proposed plan is the only thing that sets `auto`:
  a mode anyone can set stops being an answer to "where did this week come
  from?".
- Unknown fields on `/agent` requests are refused with a 422 naming them rather
  than silently dropped. A contract with a program on another machine should
  not have a failure mode where both sides think the call worked.
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

- `servings_made=0` when logging a cook reached the check constraint and came
  back a 500; it is bounded in the schema now, so a bad request is answered as
  one. Same shape as the PATCH-null fix.
- A malformed backup raised out of the restore endpoint instead of returning a
  400, and left the session holding uncommitted deletes. It rolls back and
  reports the problem now, so "nothing was changed" is true rather than likely.

- PATCH with an explicit null on a NOT NULL column returned a 500. Every field
  on a PATCH schema is optional, but `{"title": null}` is *set*, so it survived
  `exclude_unset`, reached the column as None and surfaced as an
  IntegrityError — the app blaming itself for a bad request. A `PatchModel`
  base now rejects it with a 422 naming the fields. Nullable columns are
  deliberately still clearable: `source_url: null` is a legitimate edit.
  (From a patch by John; extended from the two schemas it covered to all seven
  PATCH surfaces, which had the same hole — 18 separate 500s.)
- `PATCH /drafts/{id}` with a null payload previously answered 200 and
  silently ignored it. It is a 422 now: a request that changed nothing should
  not report success.
- A 422 whose `detail` is FastAPI's list of field errors crashed the import
  page outright — React refuses to render an object as a child, so the whole
  page became "Application error". Error bodies are flattened to text before
  display, and the promote handler now checks the shape before treating a 422
  as a validation result.

- Ingredient lines written as `500g beef mince` were filed as instructions:
  the amount and unit were only split apart inside the ingredient parser, and
  the code deciding whether a line *was* an ingredient never got that far.
- An amountless line among the ingredients ("salt and pepper to taste") became
  a step when the recipe had no `Ingredients:` heading. What makes it an
  ingredient is sitting in a run of them, so that is now the rule — and the
  run ends at the first line that reads like a sentence.
- `"stock"` appeared in both the spice and pantry keyword lists, so its column
  was decided by the order of the checks rather than by anything meaningful.
  It now matches how the recipes already in the library are filed, and the two
  lists are asserted disjoint.

- The scale row's preset chips only lit up at 0.5/1/1.5/2× of the recipe's
  yield, so a meal planned for ten from a recipe serving four left every chip
  unlit and the control read as dead. A target no preset can express now shows
  its real multiplier as a lit readout.
- The servings field committed on every keystroke, navigating and refetching
  for "1" on the way to "10", and could not be cleared. It now commits on blur
  or Enter, with Escape reverting.
- The recipe header showed the scaled serving count next to unscaled prep and
  cook times, directly above a line saying the saved recipe was unchanged. It
  shows the recipe's own yield now.
- Six nav links didn't fit at phone width, so every page scrolled sideways; the
  nav wraps instead. Ingredient columns stack to one below the `sm` breakpoint.
- Ingredient rows in the recipe form overflowed their column and overlapped the
  next one: an `<input>` has an intrinsic minimum width, so `flex-1` alone
  could not shrink the name field.

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
