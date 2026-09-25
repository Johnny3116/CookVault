# cookvault-assistant — ChefNexus

ChefNexus is CookVault's cooking assistant: a local Qwen (via Ollama) with a small,
fixed set of tools onto CookVault's `/agent` surface. It answers cooking
questions, reads the cookbook and the calendar, and **proposes** recipes and
weeks. It never writes one: every write it can make is a draft that waits for
John in the review queue.

The spec it was built to is [`Qwen-Integration.md`](./Qwen-Integration.md).
This file is what was actually built.

```
browser  ──►  frontend /api/assistant/*  ──►  assistant :8500  ──►  Ollama (qwen3:8b)
                (checks the session          (bounded tool loop)    │
                 cookie first)                        │              └── /api/chat, streamed
                                                      └──►  backend /agent/* (X-API-Key)
```

## What it does

| Ask | What happens |
|---|---|
| "How long do I rest a steak?" | Answered from the model, no tool |
| "What can I cook with chicken tonight?" | `search_recipes` → summarised |
| "What am I cooking Thursday?" | `get_meal_plan` for that date |
| "Plan me a cheap week" | `suggest_meal_plan` → `create_meal_plan_draft` → a proposal on `/calendar/proposals` |
| "Add my mom's chili: two pounds of beef, …" | `create_recipe_draft` → a draft on `/drafts`, with the words it came from as provenance |
| "Add chicken tacos" | Asks what goes in them. It does not invent a recipe. |
| "Import this: https://…" | `parse_recipe_source` → draft |

## The tools

Seven, generated from the same Zod schemas that validate the model's
arguments, so the description the model reads and the check its call passes
through cannot disagree. Two kinds:

- **READ** (`search_recipes`, `get_recipe`, `get_meal_plan`,
  `suggest_meal_plan`, `parse_recipe_source`) run on request.
- **WRITE_DRAFT** (`create_recipe_draft`, `create_meal_plan_draft`) create
  something reviewable. There is no WRITE and no DESTRUCTIVE kind, and not
  because of a policy string: the `/agent` surface this talks to has no
  promote, approve, delete or shopping-list route, and
  `backend/tests/test_agent_surface.py` pins that list.

Argument validation happens here before CookVault is called; CookVault
validates the payload again on its side. `import_method` is never sent —
CookVault records everything arriving through `/agent` as `agent`, and the
model cannot claim otherwise.

## The loop

`src/agent.ts`. One turn is:

```
model ──► tool calls? ──no──► answer
   ▲          │yes
   │     validate → execute → result (or error) back to the model
   └──────────┘   at most MAX_TOOL_ROUNDS times, then once more with no tools
```

- An unknown tool, invalid arguments, or a CookVault error all go back to the
  model in one controlled shape (`{"error": "…"}`) so it explains the failure
  instead of hallucinating past it.
- The same tool with the same arguments twice in a row is refused.
- After the round limit the model is asked once more with **no** tools, so the
  person gets a sentence rather than a spinner.
- Older turns are dropped past `CONTEXT_MESSAGES`, never summarised. A summary
  is a place for a model to quietly invent a recipe.

Every tool call is appended to `data/audit.jsonl`: conversation, model, tool,
validated arguments, outcome, duration, and the id of anything created.

## Configuration

Read from the environment (compose passes the repo's `.env`), validated at
boot by `src/config.ts`. The ones that matter:

| Variable | Default | |
|---|---|---|
| `AGENT_API_KEY` | **required**, ≥ 32 chars | The same key the backend checks |
| `COOKVAULT_ORIGIN` | `http://backend:8000` | |
| `AI_BASE_URL` | `http://127.0.0.1:11435` | Compose sets `host.docker.internal:11435`; Ollama on NexusBody is on **11435**, not 11434 |
| `AI_MODEL` | `qwen3:8b` | |
| `AI_THINK` | `false` | Qwen3 reasoning. Costs seconds on the shared 2070 |
| `AI_NUM_CTX` | `8192` | Always sent; Ollama's default truncates silently |
| `MAX_TOOL_ROUNDS` | `6` | |
| `CONTEXT_MESSAGES` | `24` | |

## Running it

```bash
bun install
AGENT_API_KEY=… AI_BASE_URL=http://nexusbody:11435 COOKVAULT_ORIGIN=http://localhost:8420 bun run dev
```

`GET /health` says whether the model and CookVault's agent door both answer;
`POST /chat` takes `{conversation_id, messages:[{role, content}]}` and streams
server-sent events (`text`, `tool`, `error`, `done`). The frontend's
`useChefNexusChat` hook is the reference client.

The service has no authentication of its own and no host port in production:
the only way in is the frontend proxy, which asks the backend's
`GET /auth/session` about the cookie first.

## Tests

```bash
bun test
```

Offline. The model and CookVault are both faked (`tests/fakes.ts`); what is
tested is the loop's behaviour around them: tool results reach the model,
failures are reported as failures, invalid arguments never reach CookVault,
repeats are refused, the round limit ends in an answer, drafts carry
provenance and come back as links. The live path is proven by hand on
NexusBody; `backend/evals` has the harness for measuring the model itself.

## Not built (yet)

- Shopping-list tools. `/agent` has no shopping-list route, and adding one
  means a write that is not a draft — a decision to make deliberately.
- Persistent conversations. Chats live in the browser tab (session storage)
  and nowhere else.
- RAG. Nothing needed it: everything ChefNexus says about the cookbook comes from
  tools, and general cooking knowledge comes from the model.
