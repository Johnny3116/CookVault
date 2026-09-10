# CookVault — MVP Specification

## 1. Overview

CookVault is a personal, single-user web application that acts as a smart cookbook and cooking assistant. It stores recipes in a structured, consistent format regardless of where they came from, helps surface new recipes based on budget/time/mood criteria, generates shopping checklists, and supports calendar-based meal planning.

This is a personal-use tool — no multi-user accounts, no billing, no public-facing concerns. Optimize for simplicity and speed of building over scalability.

## 2. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python (FastAPI) | Handles API, recipe parsing, scraping, transcript extraction, LLM calls |
| Frontend | Next.js | Responsive UI for desktop and mobile browsers |
| Database | PostgreSQL | Structured recipe/ingredient/step data |
| LLM | Lightweight LLM call (API-based) | Used narrowly for: (a) parsing recipe finder queries/intent, (b) structuring imported transcript/description text into recipe fields |
| Video/Web extraction | yt-dlp (transcripts/audio), web scraping libs (e.g. BeautifulSoup/readability) | Python ecosystem chosen partly for this |
| Auth | None or simple single password gate | No multi-tenant auth needed |

Phase 2 (post-MVP): native iOS wrapper app.

## 3. Data Model

### Recipe
- `id`
- `title`
- `source_type` (manual, youtube, tiktok, instagram, web)
- `source_url` (nullable)
- `cook_methods` (array — e.g. ["stovetop", "oven"])
- `prep_time`
- `cook_time`
- `servings`
- `estimated_cost`
- `tags` (cuisine, dietary, etc.)
- `is_favorite` (boolean)
- `created_at` / `updated_at`

### Ingredient
- `id`
- `recipe_id`
- `name`
- `quantity`
- `unit`
- `category` (enum: raw_ingredient, spice_sauce, pantry_dry_good, misc)

### Step
- `id`
- `recipe_id`
- `order`
- `instruction_text`
- `temperature` (nullable)
- `duration` (nullable)
- `notes` (nullable)

### Alternate
- `id`
- `recipe_id`
- `type` (cook_method | ingredient_substitute)
- `original_value` (e.g. "chicken" or "oven")
- `alternate_value` (e.g. "steak" or "air fryer")
- `notes` (nullable)

### ShoppingListItem
- `id`
- `recipe_id` (nullable — could be manually added)
- `name`
- `quantity`
- `unit`
- `category`
- `is_checked` (boolean)

### MealPlanEntry
- `id`
- `date`
- `recipe_id`
- `mode` (auto | manual)

## 4. Recipe Detail Page Layout

Top section — four columns:
1. **Raw Ingredients** (proteins, produce, cheese, etc.)
2. **Spices & Sauces** (seasonings, lemon juice, etc.)
3. **Pantry & Dry Goods** (rice, pasta, flour, broth, oil)
4. **Misc**

Below a visual divider:
- Step-by-step instructions, in order, each optionally showing temperature/duration/notes

Additional tab:
- **Alternates** — alternate cook methods and ingredient substitutes

## 5. Core Features (MVP Scope)

### 5.1 Recipe Storage
- Manual entry via structured form (four-column layout described above)
- Full CRUD on recipes, ingredients, steps, alternates
- Favorite flag + filtering by favorite in the library view

### 5.2 Import from Video/Web
- Input: a YouTube, TikTok, Instagram, or general web page link
- Extraction pulls from: video description, audio transcript (via yt-dlp or similar), and on-screen text where feasible for TikTok/Instagram (caption alone is known to miss 30–50% of recipe content — pull audio transcript too, not just captions)
- LLM structures extracted text into the four-column recipe format + steps
- **Always shown in a review/edit screen before saving** — no fully automatic save
- User can correct misidentified ingredients, fix quantities, reorder steps, etc.

### 5.3 Recipe Finder (Chat-Style Input)
- Free-text input box for criteria (budget, time, mood, ingredients on hand, etc.)
- Lightweight LLM parses the query into structured search criteria
- Searches saved recipes first
- If nothing sufficiently matches (or always, for variety), also performs a general web search
- Results shown side-by-side: "From your collection" vs. "New finds"
- New finds go through the same review/edit → save flow as direct imports

### 5.4 Shopping List
- Generate a checklist from one or more recipes (e.g. selected meal-plan entries for the week)
- Items grouped by the same four categories
- User manually checks off items already on hand (no auto pantry-tracking in MVP)
- Ability to manually add ad-hoc items to the list

### 5.5 Calendar / Meal Planning
- Calendar view, day-by-day
- Mode toggle per planning session:
  - **Auto-fill** — system suggests a week of meals optimized for variety and budget, avoiding repeating the same few staples
  - **Manual** — user picks meals themselves; system just tracks them on the calendar
- Planning goal: diverse, easy, tasty meals where a reasonable grocery budget covers the week

## 6. Page Flow

1. **Dashboard** — recent recipes, this week's planned meal(s)
2. **Recipe Library** — browse/filter (by category, cuisine, cook time, favorite)
3. **Recipe Detail** — four-column ingredient layout + steps + alternates tab
4. **Add/Import Recipe** — manual entry or link-based import → review/edit screen
5. **Recipe Finder** — chat-style criteria input → saved + web results
6. **Shopping List** — checklist view
7. **Calendar** — meal planning with auto-fill/manual toggle

## 7. Known Pitfalls / Lessons from Prior Art

- **TikTok/Instagram caption-only scraping is unreliable.** Caption alone misses a significant chunk of the actual recipe (missing conversions, steps mentioned only in audio). Pull audio transcript + on-screen text, not just the caption/description.
- **Unit conversion is a common trap.** Recipes mix cups, grams, ounces, milliliters inconsistently. Build a normalization layer early (e.g. base storage unit + display conversion) rather than retrofitting later.
- **Consider the Cooklang format** (cooklang.org) as a reference for a clean, structured recipe markup approach — may inform ingredient/step parsing logic even if not adopted directly.
- **Don't over-engineer auth/multi-tenancy** — this is single-user; a simple password gate (or none, if self-hosted privately) is sufficient.
- **Structured review-before-save is a deliberate quality gate** — since AI-assisted extraction from video/audio won't be perfect, the review/edit step is a core feature, not an afterthought.

## 8. Post-MVP / Future Ideas (Not in Scope for V1)

- Photo-based pantry/receipt scanning to auto-build an inventory (referenced by suggestions, never auto-assumed as "have it")
- Native iOS app (wrapping or rebuilding the web app)
