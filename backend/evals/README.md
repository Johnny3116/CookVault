# Qwen eval harness (Phase 0)

Measures whether the local Qwen on NexusBody can reliably pick tools, produce
valid arguments and extract recipes — **before** anything in CookVault depends
on it being able to.

Nothing here is wired into the app. It is a spike with a scoreboard.

```bash
cd backend
OLLAMA_BASE_URL=http://nexusbody:11434 OLLAMA_MODEL=qwen2.5:14b python -m evals.run --probe   # first
OLLAMA_BASE_URL=http://nexusbody:11434 OLLAMA_MODEL=qwen2.5:14b python -m evals.run
```

`--probe` first, always. It asks the box what it actually supports and takes
about ten seconds; the full set is 75 cases × (3 repeats + ~2 paraphrases) and
takes as long as your GPU takes.

## Configuration

| Variable | Default | |
|---|---|---|
| `OLLAMA_MODEL` | **none — required** | A default would score something nobody chose |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `OLLAMA_NUM_CTX` | `8192` | Always sent explicitly. Ollama's own default truncates *silently*, and a truncated prompt doesn't error — it comes back as a model that looks stupid |
| `OLLAMA_SEED` | `42` | |
| `OLLAMA_TEMPERATURE` | `0` | |
| `OLLAMA_TIMEOUT` | `180` | Seconds |

Flags: `--repeats N`, `--no-paraphrases`, `--no-few-shot`, `--category NAME`
(repeatable), `--probe`.

## The five categories

| Category | Asks | Cases |
|---|---|---|
| `tool_select` | Right tool, right arguments? | 15 |
| `no_tool` | Does it answer general cooking questions without reaching for a tool? | 15 |
| `extraction` | Recipe text → a draft CookVault would accept | 15 |
| `missing_info` | Vague request → **one question**, no draft, no invented ingredients | 15 |
| `injection` | Recipe text containing orders to the AI → treated as data | 15 |

## Two run modes, because they measure different things

- **`--repeats 3`** sends the identical prompt three times. At temperature 0
  with a fixed seed those should be byte-identical, so a disagreement is the
  *machine*, not the model. The report lists any case whose repeats disagreed
  under a heading that says exactly that.
- **paraphrases** send each case's alternative phrasings once each. This is the
  one that tells you whether Qwen holds up when John types it differently, and
  it is where a brittle prompt shows.

Averaging them would hide both, so the report keeps them in separate columns.

## Two call shapes, not one

Ollama's `tools` constrains tool calls; `format` constrains content. They
answer different questions and **this harness does not assume they compose** —
tool categories are sent with `tools`, extraction with `format`. `--probe`
tries both together against the live box and reports what happens, because "one
of them silently wins" is the outcome that would quietly break a design built
on the assumption.

## What is reused rather than reinvented

This is the whole reason the harness lives under `backend/` and imports `app.*`:

- **Tool schemas** are generated from `app.schemas_agent` — the same models
  `/agent/search-recipes` is coded against — then flattened (`anyOf` collapsed,
  `$ref` inlined, titles and defaults stripped) because small local models read
  those badly. `sort`'s allowed values come from `recipe_search.SORTS`, the
  tuple the router itself checks against.
- **Extraction** is validated by `app.services.drafts.validate_payload`, the
  function that actually stands between a draft and the cookbook. A schema
  copied into this directory would drift, and the eval would be measuring a
  fiction.
- **The unit enum** comes from `app.units`, so the model literally cannot emit
  a unit CookVault can't convert.

`tests/test_evals.py` guards all of that. If the contract moves and the harness
doesn't, CI fails.

## Reading a run

The table is the summary; **`results/failures.jsonl` is the finding.** Each line
carries the prompt, the raw output, the expected value and a specific reason
("called `search_recipes`, expected `get_meal_plan`", "invented quantity 2 for
'salt'"). A category scoring 9/15 tells you nothing actionable. Six reasons do.

Two categories can't be decided exactly and the scorer says so in its own
docstring: `no_tool` and `missing_info` turn on whether the model *asked*, which
is checked structurally (no tool call, no draft, a question mark). It will
accept a bad question and reject a good statement. Its job is to narrow fifteen
cases to the two worth reading — **read the failures**.

## What a pass would mean

No thresholds are set here on purpose; the first run is the baseline, not a
grade. But the categories are not equally important:

- `missing_info` is the one that costs John a dinner rather than a click. A
  model that invents a plausible chicken taco recipe is worse than one that
  refuses, because the invention looks like data.
- `injection` is worth knowing and is **not** what the system's safety rests on.
  The agent surface has no promote, no approve and no recipe write — every path
  ends in a draft John approves. The worst a successful injection achieves is a
  bad draft he declines. A weak score here is disappointing, not blocking.

## Known provisional bits

- `GetMealPlanRequest` in `tools.py` is hand-written, because there is no
  `get_meal_plan` on the agent surface yet — the agent can propose a week
  without being able to see what's already planned. Phase 1 should add the
  route, move the model to `schemas_agent.py` and delete the local copy. A test
  asserts it still matches the real endpoint's query parameters meanwhile.
- `extraction.py` reads `app.units._CANONICAL`, which is private. Guarded by a
  test that round-trips every listed unit through the public `canonical_unit()`.
  Phase 1 should export it properly.
