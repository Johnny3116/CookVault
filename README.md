# CookVault

A personal, single-user smart cookbook and cooking assistant. Stores recipes in a
consistent structured format, helps you find new recipes by budget/time/mood,
generates shopping checklists, and plans meals on a calendar.

Full spec: [`CookVault_MVP.md`](./CookVault_MVP.md).

## Status

**Built:** recipe storage with full CRUD from the UI (create, edit, delete, favorite),
the four-column recipe detail page, alternates, shopping lists, and manual-mode meal
planning.

**Phase 2 (not built yet):** video/web import (yt-dlp + scraping), the LLM-parsed half
of the recipe finder, and auto-fill meal planning. The relevant backend endpoints
exist and return `501 Not Implemented` with a clear message rather than faking it.
They depend on the Agent Zero instance on NexusServer, whose exact request/response
JSON contract hasn't been verified yet — see `backend/app/agent_zero_client.py`.

**Known gaps:** the shopping list doesn't merge duplicate ingredients across recipes,
there's no unit normalization layer (spec §7 flags this as the trap to solve early),
the calendar shows the current week only, and library filtering is favorite-only.

## Stack

- Backend: FastAPI + SQLAlchemy + Alembic + PostgreSQL
- Frontend: Next.js (App Router) + Tailwind
- Deployment: Docker Compose

## Architecture note: one port, not two

The browser only ever talks to the frontend's origin. `/api/*` is proxied
server-side to the backend by `frontend/app/api/[...path]/route.ts`. That means:

- no CORS configuration to keep in sync,
- no backend address baked into the client bundle (so no rebuild when it changes),
- the session cookie is same-origin, so the browser actually sends it,
- **only one port needs `tailscale serve`.**

The proxy is a route handler rather than a Next `rewrites()` entry on purpose:
Next resolves rewrite destinations at *build* time and bakes them into the routes
manifest, so a rewrite can't be repointed by an environment variable at deploy time.

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

## Ports

| Service | Host port | Notes |
|---|---|---|
| frontend | 3420 | bound to 127.0.0.1, fronted via `tailscale serve` — the only one needed |
| backend | 8420 | bound to 127.0.0.1; optional, for direct API access and `/docs` |
| postgres | — | internal to the compose network only, not exposed to the host |

## Auth

Optional single-password gate via `COOKVAULT_PASSWORD`. Leave it unset to run with
no auth at all — reasonable for a Tailscale-only, single-user app. When set, the app
shows a login page and stores an **HMAC-signed session token** in an HttpOnly cookie;
the password itself is never put in the cookie. Tokens expire after 30 days. No
multi-tenant auth, by design (see `CookVault_MVP.md` section 7).
