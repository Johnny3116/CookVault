# CookVault

A personal, single-user smart cookbook and cooking assistant. Stores recipes in a
consistent structured format, helps you find new recipes by budget/time/mood,
generates shopping checklists, and plans meals on a calendar.

- Full spec: [`CookVault_MVP.md`](./CookVault_MVP.md)
- Change history: [`CHANGELOG.md`](./CHANGELOG.md)

## Status

**Built and usable:** recipe storage with full CRUD from the UI (create, edit,
delete, favorite), the four-column recipe detail page, alternates, shopping lists,
manual-mode meal planning, nondestructive scaling, and the draft review queue
that everything imported will eventually pass through.

**Phase 2 (not built yet):** video/web import (yt-dlp + scraping), the LLM-parsed
half of the recipe finder, and auto-fill meal planning. The relevant backend
endpoints exist and return `501 Not Implemented` with a clear message rather than
faking it. They depend on the Agent Zero instance on NexusServer, whose exact
request/response JSON contract hasn't been verified yet — see
`backend/app/agent_zero_client.py`.

**Known gaps, in rough priority order:**

- Unit conversion has no density table, so mass and volume never combine: a
  recipe wanting 30 g of butter and another wanting 2 tbsp stay two lines.
  That's deliberate — guessing a density would be worse — but it does mean the
  list occasionally asks for the same thing twice.
- The frontend has no tests of its own; CI typechecks and builds it, but nothing
  exercises the pages. The draft lifecycle has been driven end to end in a real
  browser, but by hand rather than by anything that runs in CI.
- Drafts are proposed by hand only. `POST /import` is still a `501`: nothing
  fills a draft automatically yet, which is the next step and the reason the
  lifecycle was built first.
- Provenance can only be set when a draft is created, not edited afterwards.
  That is deliberate for now — where something came from doesn't change — but
  it means a typo in a source title is fixed by starting over.

## Stack

- Backend: FastAPI + SQLAlchemy + Alembic + PostgreSQL
- Frontend: Next.js (App Router) + Tailwind
- Deployment: Docker Compose

## The cooking pipeline

Scaling, planning and shopping are one path, not three features:

```
recipe (canonical)
    ↓  effective_scale = planned servings / recipe servings
scaled quantities
    ↓  normalize units
    ↓  merge compatible amounts
generated shopping items
```

**Scaling is nondestructive.** The stored recipe is always canonical; scaling
happens at read time via `GET /recipes/{id}?servings=N`, and the response
carries `applied_scale` so the UI can say what it did.

**The plan stores target servings, not a multiplier.** "Make this for 8" stays
meaningful if the recipe's own yield is later corrected from 4 to 6, whereas a
stored `scale = 2.0` silently becomes wrong. A recipe that never recorded its
own servings can't be scaled from, so it comes back unchanged rather than being
scaled from a guessed baseline.

**Rounding happens once, at the end.** Scale, convert and merge all run at full
Decimal precision; quantizing mid-pipeline compounds error across a week.

The shared logic lives in `backend/app/services/` so the recipe endpoint, the
shopping-list endpoint and eventually the import path all call one
implementation.

## Units and the shopping list

Recipes mix cups, grams, ounces and millilitres, and the shopping list has to
add them up — spec §7 calls this the trap to solve early. `backend/app/units.py`
is that layer: alias resolution (`Tablespoons`, `tbs`, `T` all mean one thing),
exact Decimal conversion within a dimension, and merge rules.

What it does and doesn't do, by design:

- Amounts in compatible units are summed and reported **in the unit the cook
  wrote**. Two recipes wanting 4 cups and 500 mL of stock give one `6.113 cup`
  line, not millilitres.
- Amounts that can't convert stay separate. `2 cloves` of garlic and `1 tbsp`
  of garlic are two lines, because adding them would invent a number. Mass and
  volume never combine — that needs a density this app doesn't have.
- An ingredient with no amount ("salt, to taste") merges to one line and stays
  amountless rather than becoming 0.
- Unrecognized units are not an error. `pinch`, `sprig` and `clove` are real
  recipe entries; they just only merge with themselves.

Generating is idempotent: it replaces the rows a previous generate produced and
leaves hand-added items alone, so pressing it twice gives the same list.

## Drafts: nothing enters the cookbook unreviewed

`recipes` is the cookbook. `recipe_drafts` is the staging area in front of it,
and promotion is the only route between them:

```
POST /drafts            propose            (status: draft)
PATCH /drafts/{id}      edit               (ready -> draft again)
POST /drafts/{id}/validate                 (draft <-> ready)
POST /drafts/{id}/promote   -> recipe      (status: promoted, frozen)
POST /drafts/{id}/discard                  (status: discarded, frozen)
```

The design principle this implements is **AI proposes, CookVault validates,
John approves** — and it is built and proven by hand first. When an agent is
eventually allowed to suggest recipes it gets `POST /drafts` and nothing else,
so it arrives at the same door, and every guarantee below already applies to
it.

- **A draft is allowed to be wrong.** The payload is JSONB, not columns.
  Rejecting bad payloads at the door would mean the proposals most worth
  reviewing are the ones that can never be stored to review.
- **Validation reports; it never repairs.** Silently fixing a proposal hides
  exactly what the reviewer is there to see.
- **Errors block promotion, warnings don't.** No ingredients, no steps, step
  numbers that aren't a 1..n sequence: errors. An unconvertible unit or an
  ingredient listed twice: warnings — "a handful of parsley" is a real thing
  to write, and both are also the classic shapes of a bad extraction.
- **Editing a payload drops `ready` back to `draft`.** The status is a claim
  about a specific payload; letting it survive an edit would make it a claim
  about a payload nobody checked.
- **Promotion revalidates** rather than trusting the stored status. A gate that
  trusts a cached answer is not a gate.
- **Promoted and discarded drafts are frozen.** They are the record of what was
  approved or rejected, not an editing surface.

### Provenance

`recipe_provenance` records where a draft or recipe came from: `source_type`,
`source_url`, `source_title`, `import_method`, `imported_at`, and for anything
a model touched, `agent_model` and `agent_version`.

The raw source (`original_text`) and the extracted structure
(`extracted_payload`) are stored in **separate columns on purpose**. Merged
into one, "did the transcript actually say two teaspoons, or did the model
decide that?" is unanswerable — and it is the question worth asking about an
imported recipe. Both are visible on the draft and, after promotion, on the
recipe.

One provenance row serves a draft and the recipe it becomes: promotion points
the same row at both, rather than copying it somewhere it can drift. That is
also why a promoted draft can't be deleted — deleting it would cascade the
recipe's provenance away.

## Architecture note: one port, not two

The browser only ever talks to the frontend's origin. `/api/*` is proxied
server-side to the backend by `frontend/app/api/[...path]/route.ts`. That means:

- no CORS configuration to keep in sync,
- no backend address baked into the client bundle (so no rebuild when it changes),
- the session cookie is same-origin, so the browser actually sends it,
- **only one port needs `tailscale serve`.**

The proxy is a route handler rather than a Next `rewrites()` entry on purpose:
Next resolves rewrite destinations at *build* time and bakes them into the routes
manifest, so a rewrite can't be repointed by an environment variable at deploy
time. If you ever move this back to a rewrite, `BACKEND_ORIGIN` silently stops
working.

## Project layout

```
backend/
  app/
    main.py              FastAPI app, router registration, optional CORS
    config.py            Settings, read from .env
    models.py            SQLAlchemy models
    schemas.py           Pydantic request/response schemas
    auth.py              Optional password gate, HMAC session tokens
    agent_zero_client.py Phase 2 stub — intentionally unimplemented
    routers/             One module per resource
    services/            Domain logic: scaling, shopping list, draft validation
  alembic/versions/      Migrations (0001 initial ... 0005 drafts + provenance)
  docker-entrypoint.sh   Runs migrations, then uvicorn
frontend/
  app/
    api/[...path]/       Server-side proxy to the backend
    recipes/             Detail, edit and new-recipe pages
    drafts/              The review queue: propose, validate, promote
    login/               Password gate
    ...                  Dashboard, library, finder, shopping list, calendar
  components/RecipeForm.tsx  Shared by the new and edit pages
  lib/                   api client, date helpers, formatting helpers
  types.ts               API response types
```

## Local development

```bash
cp .env.example .env
docker compose up --build
```

Migrations run automatically on backend startup (`backend/docker-entrypoint.sh`),
and Compose waits for Postgres's healthcheck before starting the backend, so there
is no manual first-run step.

- App: http://localhost:3420
- Backend directly (optional, for `/docs`): http://localhost:8420

To run the frontend outside Compose, point it at a reachable backend:

```bash
cd frontend && BACKEND_ORIGIN=http://localhost:8420 npm run dev
```

### Changing the schema

Models live in `backend/app/models.py`; every change needs a matching migration.

```bash
docker compose exec backend alembic revision --autogenerate -m "what changed"
docker compose exec backend alembic upgrade head   # or just restart the backend
docker compose exec backend alembic check          # should report no drift
```

Declare indexes on the model (via `__table_args__`) as well as in the migration,
or autogenerate will see them as drift and propose dropping them.

### Running the tests

The backend suite runs against a real PostgreSQL database rather than SQLite,
because the models use Postgres-specific types (UUID, ARRAY, native ENUM) that
SQLite would not exercise. Point `DATABASE_URL` at a throwaway database — never
the one holding your recipes, since the suite truncates tables between tests:

```bash
cd backend
pip install -r requirements-dev.txt
DATABASE_URL=postgresql+psycopg://cookvault:cookvault@localhost:5432/cookvault pytest
```

Against the Compose stack, the simplest throwaway database is a second one on
the same server:

```bash
docker compose exec postgres createdb -U cookvault cookvault_test
docker compose exec -e DATABASE_URL=postgresql+psycopg://cookvault:cookvault@postgres:5432/cookvault_test \
  backend sh -c "pip install -q -r requirements-dev.txt && pytest"
```

## CI

[`.github/workflows/ci.yml`](./.github/workflows/ci.yml) runs on every pull
request and every push to `main`:

| Job | What it catches |
|---|---|
| **backend** | Migrations that fail to apply or to reverse, models that drifted from their migration (`alembic check`), and API regressions (`pytest`) |
| **frontend** | Type errors (`tsc --noEmit`), build failures, and a `package.json`/lockfile mismatch (`npm ci`) |
| **images** | A Dockerfile that no longer builds — a broken deploy even when the app code is fine |

## Deploying on NexusBody

This is a Tailscale-only homelab app — never exposed publicly. Every service binds
its container port to `127.0.0.1` only and gets fronted by `tailscale serve`.

1. `git clone` this repo, `cp .env.example .env`, and set `COOKVAULT_PASSWORD` if
   you want the password gate (leaving it blank is reasonable on a tailnet).
2. `docker compose up -d --build` — that's it; migrations run on boot.
3. Front the single frontend port with Tailscale Serve (not Funnel):
   `tailscale serve --bg --https=443 127.0.0.1:3420`

No API URL to configure and no CORS origins to match — changing the address the app
is served on needs no rebuild.

To update: `git pull && docker compose up -d --build`. New migrations apply on
boot. The Postgres volume (`cookvault_pgdata`) is the only durable state; back it
up with:

```bash
docker compose exec -T postgres pg_dump -U cookvault cookvault > cookvault-backup.sql
```

(`-T` matters — without it Compose allocates a TTY and mangles the redirected
output.)

## Ports

| Service | Host port | Notes |
|---|---|---|
| frontend | 3420 | bound to 127.0.0.1, fronted via `tailscale serve` — the only one needed |
| backend | 8420 | bound to 127.0.0.1; optional, for direct API access and `/docs` |
| postgres | — | internal to the compose network only, not exposed to the host |

## Configuration

Everything lives in `.env` (see [`.env.example`](./.env.example)):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string; must match the compose service |
| `COOKVAULT_PASSWORD` | Optional password gate. Blank disables auth entirely |
| `CORS_ORIGINS` | Normally empty — only needed to hit the backend port directly from a browser |
| `AGENT_ZERO_BASE_URL` / `AGENT_ZERO_API_KEY` | Phase 2, not used yet |

`BACKEND_ORIGIN` is set by `docker-compose.yml` rather than `.env`; it tells the
frontend server where to proxy `/api/*` and is never seen by the browser.

## Auth

Optional single-password gate via `COOKVAULT_PASSWORD`. Leave it unset to run with
no auth at all — reasonable for a Tailscale-only, single-user app. When set, the app
shows a login page and stores an **HMAC-signed session token** in an HttpOnly
cookie; the password itself is never put in the cookie. Tokens expire after 30
days. `/health` is deliberately left outside the gate, so it stays usable as a
liveness probe. No multi-tenant auth, by design (see `CookVault_MVP.md` §7).
