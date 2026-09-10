# CookVault

A personal, single-user smart cookbook and cooking assistant. Stores recipes in a
consistent structured format, helps you find new recipes by budget/time/mood,
generates shopping checklists, and plans meals on a calendar.

Full spec: [`CookVault_MVP.md`](./CookVault_MVP.md).

## Status

**Phase 1 (this build):** recipe storage (manual entry, full CRUD), the four-column
recipe detail page, shopping lists, and manual-mode meal planning — a genuinely usable
app end to end.

**Phase 2 (not built yet):** video/web import (yt-dlp + scraping), the LLM-parsed half
of the recipe finder, and auto-fill meal planning. The relevant backend endpoints
exist and return `501 Not Implemented` with a clear message rather than faking it.
They depend on the Agent Zero instance on NexusServer, whose exact request/response
JSON contract hasn't been verified yet — see `backend/app/agent_zero_client.py`.

## Stack

- Backend: FastAPI + SQLAlchemy + Alembic + PostgreSQL
- Frontend: Next.js (App Router) + Tailwind, fetching the backend API client-side
- Deployment: Docker Compose

## Local development

```bash
cp .env.example .env
docker compose up --build
```

Run migrations the first time (and after any schema change):

```bash
docker compose exec backend alembic upgrade head
```

- Backend: http://localhost:8420 (interactive docs at `/docs`)
- Frontend: http://localhost:3420

## Deploying on NexusBody

This is a Tailscale-only homelab app — never exposed publicly.

1. Before first deploy, re-check `docker ps` on NexusBody. The ports below were
   picked from a port sweep done on a different session and aren't guaranteed free
   by the time you actually deploy.
2. Remove the old dead `recipevault` container/project first
   (`C:\Users\Nexus\Documents\Projects\2-Testing\RecipeVault\`) to avoid any name
   confusion — confirmed obsolete.
3. `git clone` this repo, copy `.env.example` to `.env` and fill in real values.
   **Important:** set `COOKVAULT_PUBLIC_API_URL` to the Tailscale address the backend
   will actually be reachable at (e.g. `https://nexusbody.tail344870.ts.net:8420`) —
   this gets baked into the frontend at build time, and the default (`localhost:8420`)
   only works when viewing the page from the same machine running compose. Anyone
   viewing from another device over Tailscale needs the real address here.
4. `docker compose up -d --build`, then `docker compose exec backend alembic upgrade head`.
5. Front it with Tailscale Serve (not Funnel) — e.g. `tailscale serve --bg 3420`.

## Ports

| Service | Host port | Notes |
|---|---|---|
| frontend | 3420 | placeholder — verify free on target host before deploying |
| backend | 8420 | placeholder — verify free on target host before deploying |
| postgres | — | internal to the compose network only, not exposed to the host |

## Auth

Single optional password gate via the `COOKVAULT_PASSWORD` env var. Leave it unset to
run with no auth at all — reasonable for a Tailscale-only, single-user app. No
multi-tenant auth, by design (see `CookVault_MVP.md` section 7).
