# CookVault

A personal, single-user smart cookbook and cooking assistant. Stores recipes in a
consistent structured format, helps you find new recipes by budget/time/mood,
generates shopping checklists, and plans meals on a calendar.

- Full spec: [`CookVault_MVP.md`](./CookVault_MVP.md)
- Change history: [`CHANGELOG.md`](./CHANGELOG.md)

## Status

**Built and usable:** recipe storage with full CRUD from the UI (create, edit,
delete, favorite), the four-column recipe detail page, alternates, shopping lists
grouped by aisle, meal planning by hand and by proposal, nondestructive scaling,
the draft review queue that everything imported passes through, import from a URL
or pasted text, import from a cooking video's description and transcript,
cooking history, a pantry, whole-library backup and restore, the `/agent`
tool surface, and **ChefNexus** — a local-model cooking assistant that reads the
cookbook through that surface and proposes drafts into the same queue. See
[ChefNexus](#chefnexus-the-assistant) and [`cookvault-assistant/README.md`](./cookvault-assistant/README.md).

**The front-end is the Lovable design.** Glass panels, DM Sans and Fraunces,
the dashboard-first layout with the week and the shopping list up top, and ChefNexus
in the corner. It is a TanStack Start app run with Bun; every page the old
Next.js front-end had was rebuilt in it.

**Auto-fill meal planning is built and needed no model at all.** "Diverse" is
arithmetic over the cook log, so CookVault does it itself and shows its working
— see [Proposed weeks](#proposed-weeks-auto-fill-and-the-agent).

**Still not built:** the outbound half of the Agent Zero integration —
CookVault *calling* Agent Zero, which both the recipe finder's web-search half
and any structuring of a video transcript would use. It is still blocked on a
request/response contract nobody has verified against the live instance on
NexusServer; `backend/app/agent_zero_client.py` raises rather than guessing.
The inbound half needs none of it, because there CookVault is the server.

**Video import has not been run against a live site.** The container it was
built in cannot reach YouTube, so every test replaces the one function that
touches the network, and the caption reader is proven against real subtitle
fixtures. The yt-dlp call itself is unproven until it runs on NexusBody.

**Known gaps, in rough priority order:**

- Unit conversion has no density table, so mass and volume never combine: a
  recipe wanting 30 g of butter and another wanting 2 tbsp stay two lines.
  That's deliberate — guessing a density would be worse — but it does mean the
  list occasionally asks for the same thing twice.
- The frontend has no tests of its own; CI typechecks and builds it, but nothing
  exercises the pages. The draft lifecycle has been driven end to end in a real
  browser, but by hand rather than by anything that runs in CI.
- ChefNexus cannot touch the shopping list. `/agent` has no shopping-list route, and
  adding one means the first agent write that is not a draft — worth deciding
  on purpose rather than slipping in.
- ChefNexus's conversations live in the browser tab and nowhere else. Reload keeps
  them; a new tab starts fresh.
- A video's transcript is kept for you to read, not turned into ingredients.
  Structuring speech needs a model, and CookVault does not call one itself —
  though one can propose a recipe through `/agent/recipe-drafts`.
- Video import covers YouTube, TikTok and Instagram, and nothing else, by
  design. A video host that publishes captions but isn't on that list needs a
  line added to `SUPPORTED_HOSTS` and a moment's thought about it.
- The recipe finder still searches only saved recipes. The "new finds" half
  needs web search, which is the outbound Agent Zero client.
- The text parser is a heuristic. It reads the shapes real recipes use, but an
  unusual layout will land wrong in the draft and need fixing by hand.
- The agent surface has no rate limiting. It is single-user and Tailscale-only,
  and the key is the only thing in front of it; that is a deliberate scope call,
  not an oversight.
- Provenance can only be set when a draft is created, not edited afterwards.
  That is deliberate for now — where something came from doesn't change — but
  it means a typo in a source title is fixed by starting over.
- Leftovers and freezer tracking are deliberately not built. That is the
  feature that wakes up three weeks later as `FoodInventoryLot` and
  `PortionAllocation`; the pantry is kept quantity-free for the same reason.
- Aisle rules match words, not meaning. A term you haven't added lands in
  `other` until you add it — there is no cleverness making a guess.

## Stack

- Backend: FastAPI + SQLAlchemy + Alembic + PostgreSQL
- Frontend: TanStack Start (React 19, Vite, Tailwind 4) on Bun
- Assistant: Bun + TypeScript, Ollama (qwen3:8b) on NexusBody
- Deployment: Docker Compose

## ChefNexus, the assistant

ChefNexus is the "Ask ChefNexus" button in the corner. It is a local Qwen with seven
tools onto `/agent`, and the whole design fits in one sentence: **ChefNexus
proposes, CookVault validates, John approves.** It can read the library, the
calendar and the ranked meal-plan candidates; it can propose a recipe draft or
a week; it cannot promote, approve, delete or touch the shopping list, because
the surface it talks to has none of those routes.

```
browser ─► frontend /api/assistant/* ─► cookvault-assistant ─► Ollama (qwen3:8b)
            (session cookie checked      (bounded tool loop)        │
             against /auth/session)             └─► backend /agent/* (X-API-Key)
```

The assistant service is in [`cookvault-assistant/`](./cookvault-assistant/)
with its own README; the spec it was built to is
[`cookvault-assistant/Qwen-Integration.md`](./cookvault-assistant/Qwen-Integration.md).
It shares `AGENT_API_KEY` with the backend and reads Ollama at
`AI_BASE_URL`. If either is unreachable, ChefNexus says so in its panel and the rest
of CookVault carries on unaffected.

What was added on the backend for it: `GET /agent/meal-plan` (the calendar
with titles, so "what am I cooking Thursday?" is answerable — the gap the
eval harness had flagged) and `GET /auth/session`, the yes/no the frontend
proxy asks before forwarding a chat.

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
John approves** — and it was built and proven by hand first. That turned out to
matter: when the agent surface arrived it got its own door into this same
queue and nothing else, so every guarantee below already applied to it on the
first day. See [The agent surface](#the-agent-surface).

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

### Importing

`POST /import` (a URL), `POST /import/video` (a cooking video) and
`POST /import/paste` (text) all create a **draft**. There is no flag to skip
that: an importer reads something somebody else wrote and is sometimes wrong
about it, so the review queue is where its output belongs by construction
rather than by convention.

All three are deterministic — no model, no API key:

- **A URL** is fetched and its `schema.org/Recipe` JSON-LD read if present.
  Most recipe sites publish it because Google asks them to, and it carries the
  amounts the author actually typed, so this is extraction rather than
  guessing. Without it, the page text goes through the same heuristic as a
  paste, which is rougher.
- **A video** (`services/video_import.py`) has both its description and its
  spoken transcript read, and keeps both. The spec's first listed pitfall is
  that captions alone miss 30–50% of a recipe, so when the description says
  "season to taste" and the video says "a teaspoon of salt", the second one is
  there to be found. Only the description is *structured* — see below.
- **Pasted text** goes through `services/recipe_text.py`: amounts ("1 1/2",
  "½", "400g", "2-3" → its lower bound), units, and a first guess at which of
  the four columns each ingredient belongs to. Step numbers come out as 1..n
  by construction, so a parsed draft never trips validation's sequence check
  on the parser's account.

The parser is a heuristic and will sometimes be wrong; it is only defensible
because nothing it produces reaches the cookbook unreviewed.

**URLs are checked before they are fetched.** The server fetches whatever it
is handed, so `check_url` resolves the host first and refuses loopback,
private, link-local, reserved and multicast addresses, and anything that is
not http(s). A recipe never lives at a private address, and without this a
pasted link could make CookVault fetch from inside the Tailscale network and
store the reply.

**Speech is not parsed into ingredients.** Descriptions are written as lists
and the line heuristic handles them. A transcript is prose, and running the
same parser over it produces the ingredient *"guanciale and you want to render
that slowly"* — worse than nothing, because it looks like data. So when the
description holds no recipe, the draft arrives with the title, an empty recipe,
the transcript attached and a note saying plainly that it could not be
structured. A draft that admits it beats one that is confidently wrong, and the
transcript is still worth having in the queue to work from.

**Rolling captions** are the one real parsing problem. YouTube's automatic
captions are written to be read two lines at a time, so each cue repeats the
tail of the one before and adds a few words; concatenated naively a transcript
reads *"so today we're making a so today we're making a carbonara so today
we're making a carbonara and the first…"* — three times its real length.
`services/transcripts.py` drops a line that repeats what was just emitted, and
only when it is consecutive, because someone saying the same thing twice a
minute apart said it twice. VTT, SRT and json3; json3 preferred because it has
no such repetition to undo. Written captions beat automatic ones, for the same
reason `import_method` exists.

**Video import is allowlisted** to YouTube, TikTok and Instagram, unlike
`/import`. That endpoint fetches a page CookVault then parses itself; this one
hands a URL to yt-dlp, a large extractor that follows the site's own redirects
to wherever the media lives. `check_url` guards the address it was given and
cannot guard everywhere that library then goes, so a short list of hosts is the
smaller thing to reason about — and general web pages already have a path.
Both checks run: a hostname on the list could still resolve somewhere private.

**Still not built:** model-assisted structuring, which is what would make the
transcript worth more than a reference to read while editing. It needs a
verified Agent Zero contract (`app/agent_zero_client.py`). When it lands it
fills `extracted_payload` from `original_text` and creates a draft through the
same function; `import_method` is what tells them apart afterwards.

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

## Aisles, history, pantry and backups

**Aisle is a different axis from ingredient category.** Category is what a
thing *is* when you cook with it (raw / spice / pantry / misc); aisle is where
you walk to pick it up. Fresh parsley is a `spice_sauce` ingredient in the
produce aisle.

The mapping lives in `aisle_rules` — rows, not a dict in the source — because
the right answer is personal and shop-specific and should be editable without a
deploy. Migration `0006` seeds 161 terms as a starting point you own. The
longest matching term wins, so `chicken stock` beats `chicken` and lands in
pantry; terms match whole words, so `ham` doesn't fire on `hammer`; nothing
matching is `other` rather than a guess. `GET /aisles/resolve?name=…` says
which rule decided, because a mapping you can't interrogate is one you fight.

An item's aisle is resolved per response, not stored, so correcting a rule
corrects every line that relied on it. `aisle_override` is there for when you
know better than the rules; clearing it hands the line back.

**Cooking history** (`cook_log`) records what was actually made and when,
separately from the plan — a plan is an intention, a log is a record, and
nothing should rewrite the second because the first changed. The rating and
note belong to the occasion, not the recipe: "too salty" is about the night you
cooked it. `times_cooked` and `last_cooked_on` are derived from the log rather
than kept as counters, because a counter and a log can disagree. The library's
**"Not made in ages"** sort is the question this exists to answer.

**The pantry** is a list of names and notes. No quantities, no expiry dates,
no lots — tracking how much olive oil is left turns a cookbook into inventory
software, and the person who has to keep it accurate is the one who wanted to
cook dinner. Its one job is to flag a shopping line as something you probably
already have. **It never removes a line:** silently under-buying is worse than
buying a second jar of cumin.

### Backups

`GET /backup/export` returns the whole library as JSON; `POST /backup/restore`
puts it back, replacing everything, and requires `confirm: "replace"` in the
body because an accidental restore can't be undone from inside the app.

Three decisions make the backup checkable rather than merely plausible:

- **Ids are preserved.** A restore that renumbers produces a library that looks
  right and compares unequal — and then a good backup is indistinguishable from
  a bad one.
- **Restore is one transaction.** A half-restored library is the worst outcome
  available, so a malformed file rolls back and changes nothing.
- **The format is versioned**, and an unrecognised version is refused rather
  than half-imported.

Decimal quantities export as strings, so a third of a cup survives as the
number it was. Derived values (`times_cooked`, resolved aisles) are deliberately
absent — exporting them would invite a restore that disagrees with its own data.

**Restore testing runs in CI.** `test_a_full_library_survives_a_round_trip`
builds a library with a row in every table, exports it, wipes everything,
restores, and compares the *whole* export for equality. Spot-checking a few
fields is how a backup that quietly drops a column passes its own tests for a
year.

## The agent surface

**CookVault is the server, not the client.** Agent Zero calls *in*, over a
separate door at `/agent`. That inversion is the whole design, and it is what
made this buildable: an agent calling in needs no guess about anyone else's wire
format, and every write it can attempt is one CookVault wrote and validates.

**AI proposes. CookVault validates. John approves.** In endpoints:

| Tool | Writes? | What it does |
|---|---|---|
| `GET /agent/manifest` | no | The tool list and the guarantees, served by the thing that implements them |
| `POST /agent/parse-recipe-source` | no | CookVault's own deterministic parser, on text or a URL |
| `POST /agent/search-recipes` | no | The library by tags, time, cost, ingredients and cooking history |
| `GET /agent/recipes/{id}` | no | One recipe in full, provenance included |
| `POST /agent/suggest-meal-plan` | no | Ranked candidates per day, with the reason for each score |
| `POST /agent/recipe-drafts` | draft | Propose a recipe |
| `PATCH /agent/recipe-drafts/{id}` | draft | Revise one of its own, while unsettled |
| `GET /agent/recipe-drafts/{id}` | no | Read one of its own back, with the current verdict |
| `POST /agent/meal-plan-drafts` | draft | Propose a week |

Every write creates or edits a draft. **Nothing here writes a recipe, a meal
plan entry, a shopping list or a backup**, and promotion and approval are not on
this surface at all. That list is pinned as a literal in
`tests/test_agent_surface.py`: adding an endpoint fails the suite until someone
writes down what it is and why the agent may have it, and the manifest is
asserted to describe exactly the routes that are mounted.

**A separate door, in both directions.** John's password gate issues a browser
cookie; the agent presents `X-API-Key`. A cookie does not open `/agent`, so a
mistake in the web UI cannot reach tools the UI has no business calling — and a
leaked agent key is not a way to promote a draft or restore a backup. Both
directions have tests.

**Off unless configured.** With `AGENT_API_KEY` unset the surface answers 503
rather than coming up open because nobody set a variable. A key under 32
characters refuses to boot: it is the only credential in front of a surface that
can write, so a weak one should be a startup complaint rather than a 503 nobody
can explain.

**Authorship is recorded, not inferred.** `recipe_drafts.created_by` is a fact
about which door the request came through, not a claim the content makes about
itself — which is what makes "the agent cannot edit a draft John started"
enforceable. The agent also cannot *read* one: that is a 404 rather than a 403,
because the two differ only in whether the answer confirms the row exists.

**Unknown fields are refused, not dropped.** This is a contract with a program
on another machine, so a misspelled field comes back as a 422 naming it. Ignored
input is the failure mode where both sides think the call worked and only one of
them is right. `import_method` is the field most likely to be tried and the one
this surface will never accept — anything arriving here is recorded as `agent`.

An invalid *recipe* proposal is accepted and reported rather than refused: a
draft is allowed to be wrong, that is what the queue is for, and rejecting the
proposals most worth reviewing would leave the agent guessing. A *plan* naming a
recipe id that does not exist is refused, because that is not a judgement call
about content — it is a reference that cannot resolve, and accepting it would
queue something that can never be approved.

## Proposed weeks: auto-fill and the agent

The spec asks auto-fill for "diverse, easy, tasty meals where a reasonable
grocery budget covers the week". Three of those are arithmetic and one is not:

- **Easy** and **within budget** are the time and cost filters.
- **Diverse** is the cook log — how long since this was last made is a number.
- **Tasty** is not something CookVault can know, and it does not pretend to.

So the variety arithmetic lives in `services/meal_planning.py`, deterministic
and explainable, and `POST /meal-plan/auto-fill` needs **no model at all**. A
model asked to "avoid repeating the same staples" will produce a plausible
answer that quietly repeats staples and nothing about the answer will say so;
days-since-last-cooked is checkable, and every meal comes back with the sentence
that put it there.

What the agent is actually for is the part a number cannot settle: taste,
balance across a week, what suits a Tuesday, what you said last time. It gets
ranked candidates from `suggest_meal_plan` and makes those judgements.

Candidates are **dealt round-robin** across the days rather than repeated.
Handing every day the same top five would make "candidates for seven days" a
list of five, and a caller taking the first each day would cook the same thing
all week.

**A proposal is not a plan.** Either way — CookVault's or the agent's — the
result is a `meal_plan_draft` and the calendar is untouched until you approve
it, at `/calendar/proposals`, where any meal can be swapped or dropped first. A
plan you can only take whole or reject whole is one you reject.

Approving is the only way an entry is ever recorded as `auto`. `POST /meal-plan`
with `mode: "auto"` is a 400 pointing here: a mode anyone can set stops being an
answer to "where did this week come from?". References are resolved again at
approval rather than trusted from when the plan was made — a recipe can be
deleted in between — and nothing is written if any of them fail.

## Architecture note: one port, not two

The browser only ever talks to the frontend's origin. `/api/*` is proxied
server-side by the Start server route in `frontend/src/routes/api/$.ts`:
`/api/assistant/*` goes to ChefNexus (after the session cookie has been checked
against the backend), everything else to the backend. That means:

- no CORS configuration to keep in sync,
- no backend or assistant address in the client bundle (so no rebuild when
  one changes — both are read from the environment per request),
- the session cookie is same-origin, so the browser actually sends it,
- the assistant needs no port on the host and no auth of its own,
- **only one port needs `tailscale serve`.**

## Project layout

```
backend/
  app/
    main.py              FastAPI app, router registration, optional CORS
    config.py            Settings, read from .env
    models.py            SQLAlchemy models
    schemas.py           Pydantic request/response schemas
    auth.py              Optional password gate, HMAC session tokens
    agent_auth.py        The separate X-API-Key door for /agent
    schemas_agent.py     The contract Agent Zero is coded against
    agent_zero_client.py The OUTBOUND direction — still unimplemented, raises
    routers/agent.py     The whole agent tool surface, in one file
    routers/             One module per resource
    services/            Domain logic: scaling, shopping list, validation,
                         recipe-text parsing, web import, aisles, backup,
                         recipe search, meal planning
  alembic/versions/      Migrations (0001 initial ... 0011 video import)
  docker-entrypoint.sh   Runs migrations, then uvicorn
frontend/                TanStack Start, file-based routes
  src/routes/
    __root.tsx           Shell: nav, ChefNexus, toasts
    api/$.ts             Server-side proxy: /api/* → backend, /api/assistant/* → ChefNexus
    index.tsx            Dashboard: the week, the list, recent recipes
    recipes/             Detail (with scaling), edit, new
    drafts/              The review queue: import, propose, validate, promote
    calendar/            The week, and proposals/ waiting to be approved
    ...                  Library, finder, shopping list, pantry, login
  src/components/
    RecipeForm.tsx       Shared by new, edit and draft review
    chef-nexus/          The chat panel and the SSE client hook
  src/lib/               api client, date/format helpers, recipe helpers
  src/styles.css         The Lovable theme; styles.cookvault.css the additions
  src/types.ts           API response types
cookvault-assistant/     ChefNexus. See its README
  src/agent.ts           The bounded tool loop
  src/tools/             The seven tools, Zod-validated
  src/provider/          Ollama, behind a small interface
  prompts/system.md      ChefNexus's instructions
  tests/                 Offline, against a faked model and a faked CookVault
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
- ChefNexus directly (optional, `/health`): http://localhost:8520

Compose reaches Ollama at `host.docker.internal:11435`; set `AI_BASE_URL` in
`.env` if it lives elsewhere.

To run the frontend or the assistant outside Compose, point them at a
reachable backend:

```bash
cd frontend && BACKEND_ORIGIN=http://localhost:8420 ASSISTANT_ORIGIN=http://localhost:8500 bun run dev
cd cookvault-assistant && AGENT_API_KEY=… AI_BASE_URL=http://nexusbody:11435 COOKVAULT_ORIGIN=http://localhost:8420 bun run dev
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
| **frontend** | Type errors (`tsc --noEmit`), build failures, and a `package.json`/lockfile mismatch (`bun install --frozen-lockfile`) |
| **assistant** | Type errors and the loop's behaviour (`bun test`, offline against fakes) |
| **images** | A Dockerfile that no longer builds — a broken deploy even when the app code is fine |

## Deploying on NexusBody

This is a Tailscale-only homelab app — never exposed publicly. Every service binds
its container port to `127.0.0.1` only and gets fronted by `tailscale serve`.

1. `git clone` this repo, `cp .env.example .env`, set `AGENT_API_KEY` (ChefNexus
   needs it; blank means no ChefNexus), and set `COOKVAULT_PASSWORD` if you want the
   password gate (leaving it blank is reasonable on a tailnet). Ollama must be
   reachable from Docker at `AI_BASE_URL` with `AI_MODEL` pulled.
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
| assistant | 8520 | bound to 127.0.0.1; optional, for `/health`. Chats only arrive through the frontend proxy |
| postgres | — | internal to the compose network only, not exposed to the host |

## Configuration

Everything lives in `.env` (see [`.env.example`](./.env.example)):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string; must match the compose service |
| `COOKVAULT_PASSWORD` | Optional password gate. Blank disables auth entirely |
| `CORS_ORIGINS` | Normally empty — only needed to hit the backend port directly from a browser |
| `AGENT_API_KEY` | The key that opens `/agent`. The backend checks it and ChefNexus presents it. Blank switches that surface off entirely and ChefNexus reports itself unavailable. Minimum 32 characters, enforced at startup |
| `AI_BASE_URL` / `AI_MODEL` / `AI_THINK` / `AI_NUM_CTX` / `AI_TEMPERATURE` / `MAX_TOOL_ROUNDS` | ChefNexus's model and loop settings — see `cookvault-assistant/README.md` |
| `AGENT_ZERO_BASE_URL` / `AGENT_ZERO_API_KEY` | The *outbound* direction, still not used — see `backend/app/agent_zero_client.py` |

`BACKEND_ORIGIN` and `ASSISTANT_ORIGIN` are set by `docker-compose.yml` rather
than `.env`; they tell the frontend server where to proxy `/api/*` and are never
seen by the browser.

## Auth

Optional single-password gate via `COOKVAULT_PASSWORD`. Leave it unset to run with
no auth at all — reasonable for a Tailscale-only, single-user app. When set, the app
shows a login page and stores an **HMAC-signed session token** in an HttpOnly
cookie; the password itself is never put in the cookie. Tokens expire after 30
days. `/health` is deliberately left outside the gate, so it stays usable as a
liveness probe. No multi-tenant auth, by design (see `CookVault_MVP.md` §7).

`AGENT_API_KEY` is a **separate credential for a separate surface**, not a
second password. It opens `/agent` and nothing else, and the session cookie does
not open `/agent` — see [The agent surface](#the-agent-surface).
