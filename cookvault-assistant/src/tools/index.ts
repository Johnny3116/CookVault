import { z } from "zod";

import { ToolRegistry, type Tool } from "./registry.ts";

/** The tools Sage has. Each wraps one call on CookVault's /agent surface and
 *  reshapes the answer for a model: fewer fields, no nulls to trip over. */

const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "YYYY-MM-DD");

// --------------------------------------------------------------------------
// reading
// --------------------------------------------------------------------------

const searchSchema = z.object({
  text: z.string().optional().describe("Words to match in the title."),
  tags: z.array(z.string()).optional().describe("Any of these tags, e.g. italian, weeknight."),
  cook_methods: z.array(z.string()).optional().describe("Any of these, e.g. stovetop, oven, air fryer."),
  includes_ingredients: z
    .array(z.string())
    .optional()
    .describe("Recipes that USE all of these ingredients (for using something up). Not recipes makeable from only these."),
  max_total_time: z.number().int().positive().optional().describe("Prep plus cook, in minutes."),
  max_cost: z.number().positive().optional().describe("Estimated cost ceiling, in dollars."),
  favorite: z.boolean().optional().describe("Only favorites when true."),
  never_cooked: z.boolean().optional().describe("Only recipes never cooked when true."),
  sort: z.enum(["updated", "last_cooked", "most_cooked", "title", "cost"]).optional().describe("last_cooked = not made in ages first."),
  limit: z.number().int().min(1).max(25).optional(),
});

type AgentRecipeSummary = {
  id: string;
  title: string;
  tags: string[];
  cook_methods: string[];
  total_time: number | null;
  servings: number | null;
  estimated_cost: string | null;
  is_favorite: boolean;
  times_cooked: number;
  last_cooked_on: string | null;
};

function summarise(recipe: AgentRecipeSummary) {
  return {
    id: recipe.id,
    title: recipe.title,
    tags: recipe.tags,
    cook_methods: recipe.cook_methods,
    ...(recipe.total_time !== null ? { total_minutes: recipe.total_time } : {}),
    ...(recipe.servings !== null ? { servings: recipe.servings } : {}),
    ...(recipe.estimated_cost !== null ? { estimated_cost: Number(recipe.estimated_cost) } : {}),
    favorite: recipe.is_favorite,
    times_cooked: recipe.times_cooked,
    ...(recipe.last_cooked_on ? { last_cooked_on: recipe.last_cooked_on } : {}),
  };
}

export const searchRecipes: Tool<z.infer<typeof searchSchema>> = {
  name: "search_recipes",
  kind: "READ",
  description:
    "Search the saved recipe library by title words, tags, cooking time, cost, ingredients and cooking history. " +
    "Use this to find recipes the person already has. Every filter is optional; no filters returns the whole library.",
  schema: searchSchema,
  label: (args) => (args.text ? `Searching recipes for “${args.text}”…` : "Searching your recipes…"),
  async execute(args, ctx) {
    const body = {
      ...(args.text ? { text: args.text } : {}),
      tags: args.tags ?? [],
      cook_methods: args.cook_methods ?? [],
      includes_ingredients: args.includes_ingredients ?? [],
      ...(args.max_total_time ? { max_total_time: args.max_total_time } : {}),
      ...(args.max_cost ? { max_cost: args.max_cost } : {}),
      ...(args.favorite !== undefined ? { favorite: args.favorite } : {}),
      never_cooked: args.never_cooked ?? false,
      sort: args.sort ?? "updated",
      limit: args.limit ?? 10,
    };
    const result = await ctx.cookvault.post<{ total_matched: number; results: AgentRecipeSummary[] }>("/agent/search-recipes", body);
    return {
      content: { total_matched: result.total_matched, results: result.results.map(summarise) },
      summary: `${result.total_matched} ${result.total_matched === 1 ? "recipe" : "recipes"}`,
    };
  },
};

const getRecipeSchema = z.object({
  recipe_id: z.string().uuid().describe("The recipe's id, as returned by search_recipes."),
});

type RecipeDetail = {
  id: string;
  title: string;
  tags: string[];
  cook_methods: string[];
  prep_time: number | null;
  cook_time: number | null;
  servings: number | null;
  estimated_cost: string | null;
  is_favorite: boolean;
  times_cooked: number;
  last_cooked_on: string | null;
  source_url: string | null;
  ingredients: { name: string; quantity: string | null; unit: string | null; category: string }[];
  steps: { order: number; instruction_text: string; temperature: string | null; duration: string | null; notes: string | null }[];
  alternates: { type: string; original_value: string; alternate_value: string; notes: string | null }[];
};

export const getRecipe: Tool<z.infer<typeof getRecipeSchema>> = {
  name: "get_recipe",
  kind: "READ",
  description: "Read one saved recipe in full: ingredients, steps and alternates. Needs an id from search_recipes; it cannot look a recipe up by name.",
  schema: getRecipeSchema,
  label: () => "Opening the recipe…",
  async execute(args, ctx) {
    const r = await ctx.cookvault.get<RecipeDetail>(`/agent/recipes/${args.recipe_id}`);
    return {
      content: {
        id: r.id,
        title: r.title,
        tags: r.tags,
        cook_methods: r.cook_methods,
        ...(r.prep_time !== null ? { prep_minutes: r.prep_time } : {}),
        ...(r.cook_time !== null ? { cook_minutes: r.cook_time } : {}),
        ...(r.servings !== null ? { servings: r.servings } : {}),
        ...(r.source_url ? { source_url: r.source_url } : {}),
        ingredients: r.ingredients.map((i) => ({
          name: i.name,
          ...(i.quantity !== null ? { quantity: Number(i.quantity) } : {}),
          ...(i.unit ? { unit: i.unit } : {}),
          category: i.category,
        })),
        steps: r.steps
          .slice()
          .sort((a, b) => a.order - b.order)
          .map((s) => [s.instruction_text, s.temperature, s.duration, s.notes].filter(Boolean).join(" — ")),
        alternates: r.alternates.map((a) => `${a.type === "cook_method" ? "method" : "ingredient"}: ${a.original_value} → ${a.alternate_value}${a.notes ? ` (${a.notes})` : ""}`),
      },
      summary: r.title,
      links: [{ kind: "recipe", id: r.id, title: r.title }],
    };
  },
};

const mealPlanSchema = z.object({
  start: isoDate.optional().describe("First day to include, YYYY-MM-DD. Omit for no lower bound."),
  end: isoDate.optional().describe("Last day to include, YYYY-MM-DD. Omit for no upper bound."),
});

type PlannedEntry = { date: string; recipe_id: string; recipe_title: string; meal_type: string | null; servings: number | null; mode: string };

export const getMealPlan: Tool<z.infer<typeof mealPlanSchema>> = {
  name: "get_meal_plan",
  kind: "READ",
  description: "What is already on the meal-plan calendar for a date range, with recipe titles. Use it for “what am I cooking on…” and before proposing a week.",
  schema: mealPlanSchema,
  label: () => "Checking the meal plan…",
  async execute(args, ctx) {
    const result = await ctx.cookvault.get<{ entries: PlannedEntry[] }>("/agent/meal-plan", { start: args.start, end: args.end });
    return {
      content: {
        entries: result.entries.map((e) => ({
          date: e.date,
          recipe_id: e.recipe_id,
          title: e.recipe_title,
          ...(e.meal_type ? { meal: e.meal_type } : {}),
          ...(e.servings !== null ? { servings: e.servings } : {}),
        })),
      },
      summary: `${result.entries.length} planned`,
    };
  },
};

const suggestSchema = z.object({
  start: isoDate.describe("First day of the week to plan, YYYY-MM-DD."),
  days: z.number().int().min(1).max(14).optional().describe("How many days. Default 7."),
  max_total_time: z.number().int().positive().optional().describe("Only recipes under this many minutes."),
  max_cost: z.number().positive().optional(),
  tags: z.array(z.string()).optional(),
});

type Suggestion = { days: { date: string; candidates: { recipe: AgentRecipeSummary; score: number; reason: string }[] }[]; note: string };

export const suggestMealPlan: Tool<z.infer<typeof suggestSchema>> = {
  name: "suggest_meal_plan",
  kind: "READ",
  description:
    "Ranked recipe candidates for each day, scored by how long since each was last cooked, with the reason for each score. " +
    "Stores nothing. Pick from these when proposing a week with create_meal_plan_draft.",
  schema: suggestSchema,
  label: () => "Ranking what hasn't been cooked in a while…",
  async execute(args, ctx) {
    const result = await ctx.cookvault.post<Suggestion>("/agent/suggest-meal-plan", {
      start: args.start,
      days: args.days ?? 7,
      per_day: 3,
      ...(args.max_total_time ? { max_total_time: args.max_total_time } : {}),
      ...(args.max_cost ? { max_cost: args.max_cost } : {}),
      tags: args.tags ?? [],
    });
    return {
      content: {
        note: result.note,
        days: result.days.map((d) => ({
          date: d.date,
          candidates: d.candidates.map((c) => ({ recipe_id: c.recipe.id, title: c.recipe.title, reason: c.reason })),
        })),
      },
      summary: `${result.days.length} days`,
    };
  },
};

const parseSchema = z
  .object({
    text: z.string().min(1).optional().describe("Recipe text, as written."),
    url: z.string().url().optional().describe("A public recipe page. CookVault fetches it; private addresses are refused."),
  })
  .refine((v) => (v.text === undefined) !== (v.url === undefined), { message: "Send exactly one of text or url." });

type Parsed = { payload: Record<string, unknown>; method: string; source_text: string; issues: { severity: string; field: string; message: string }[] };

export const parseRecipeSource: Tool<z.infer<typeof parseSchema>> = {
  name: "parse_recipe_source",
  kind: "READ",
  description:
    "Read recipe text or a recipe page URL with CookVault's deterministic parser. Returns the structure it found and any doubts. " +
    "Stores nothing; propose a draft afterwards with create_recipe_draft if the person wants it kept.",
  schema: parseSchema,
  label: (args) => (args.url ? "Reading the recipe page…" : "Reading the recipe text…"),
  async execute(args, ctx) {
    const result = await ctx.cookvault.post<Parsed>("/agent/parse-recipe-source", args.text !== undefined ? { text: args.text } : { url: args.url });
    return {
      content: { method: result.method, recipe: result.payload, issues: result.issues.map((i) => `${i.severity}: ${i.field} — ${i.message}`) },
      summary: result.issues.length ? `${result.issues.length} doubts` : "parsed",
    };
  },
};

// --------------------------------------------------------------------------
// proposing
// --------------------------------------------------------------------------

const category = z.enum(["raw_ingredient", "spice_sauce", "pantry_dry_good", "misc"]);

const draftSchema = z.object({
  title: z.string().min(1).max(255),
  ingredients: z
    .array(
      z.object({
        name: z.string().min(1),
        quantity: z.number().nonnegative().optional().describe("A number. Omit if the person gave none; do not invent one."),
        unit: z.string().optional().describe("e.g. cup, tbsp, g, lb, can, clove. Omit if none."),
        category: category.optional().describe("raw_ingredient = produce, meat, dairy; spice_sauce; pantry_dry_good = rice, flour, oil, stock; misc."),
      }),
    )
    .min(1)
    .describe("Only what the person gave you."),
  steps: z.array(z.string().min(1)).min(1).describe("In order, one instruction each. Only what the person described."),
  prep_time: z.number().int().nonnegative().optional().describe("Minutes, only if stated."),
  cook_time: z.number().int().nonnegative().optional().describe("Minutes, only if stated."),
  servings: z.number().int().positive().optional().describe("Only if stated."),
  tags: z.array(z.string()).optional(),
  cook_methods: z.array(z.string()).optional(),
  source_text: z.string().optional().describe("The person's own words the recipe came from, verbatim. Kept as provenance."),
  note: z.string().optional().describe("Anything you were unsure about, for the reviewer. Never part of the recipe."),
});

type AgentDraft = { id: string; status: string; title: string | null; valid: boolean; issues: { severity: string; field: string; message: string }[] };

/** Tidy the shapes a small model reaches for before the schema sees them.
 *
 * Renaming `name` to `title`, reading a step written as `{text: …}`, turning
 * `"2"` into 2 and dropping a `servings: 0` that means "not given" are
 * normalisation: no content is added. Anything that would need inventing --
 * a missing ingredient list, a quantity that was never a number -- is left
 * for the schema to refuse, so the model asks the person instead.
 */
export function normaliseDraftArguments(raw: unknown): unknown {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return raw;
  let input = raw as Record<string, unknown>;
  // `{recipe: {...}}` or `{draft: {...}}`: the recipe one level down, with
  // the note (if any) beside it. Lift it.
  for (const wrapper of ["recipe", "draft", "payload"]) {
    const inner = input[wrapper];
    if (inner && typeof inner === "object" && !Array.isArray(inner) && input["ingredients"] === undefined) {
      const { [wrapper]: _dropped, ...rest } = input;
      input = { ...rest, ...(inner as Record<string, unknown>) };
      break;
    }
  }
  const out: Record<string, unknown> = { ...input };

  const first = (...keys: string[]) => keys.map((k) => input[k]).find((v) => v !== undefined && v !== null && v !== "");
  const title = first("title", "name", "recipe_name", "recipe_title");
  if (typeof title === "string") out["title"] = title;
  for (const key of ["name", "recipe_name", "recipe_title"]) delete out[key];

  // There is no description on a recipe. A model that sends one is usually
  // echoing the person's words, which is what source_text is for.
  if (typeof input["description"] === "string" && input["source_text"] === undefined) out["source_text"] = input["description"];
  delete out["description"];

  const steps = first("steps", "instructions", "method", "directions");
  if (Array.isArray(steps)) {
    out["steps"] = steps
      .map((step) => {
        if (typeof step === "string") return step;
        if (step && typeof step === "object") {
          const s = step as Record<string, unknown>;
          const text = s["instruction_text"] ?? s["text"] ?? s["instruction"] ?? s["step"] ?? s["description"];
          return typeof text === "string" ? text : "";
        }
        return "";
      })
      .map((text) => text.trim())
      .filter(Boolean);
  } else if (typeof steps === "string") {
    out["steps"] = steps
      .split(/\n+/)
      .map((line) => line.replace(/^\s*(\d+[.)]|[-*•])\s*/, "").trim())
      .filter(Boolean);
  }
  for (const key of ["instructions", "method", "directions"]) delete out[key];

  if (Array.isArray(input["ingredients"])) {
    out["ingredients"] = input["ingredients"].map((item) => {
      if (typeof item === "string") return { name: item.trim() };
      if (!item || typeof item !== "object") return item;
      const i = { ...(item as Record<string, unknown>) };
      if (i["name"] === undefined && typeof i["ingredient"] === "string") i["name"] = i["ingredient"];
      delete i["ingredient"];
      // "2" becomes 2. "a pinch" stays a string and the schema refuses it:
      // silently dropping it would lose what the person said.
      if (typeof i["quantity"] === "string" && i["quantity"].trim() !== "" && Number.isFinite(Number(i["quantity"]))) {
        i["quantity"] = Number(i["quantity"]);
      }
      if (i["quantity"] === null) delete i["quantity"];
      if (i["unit"] === null || i["unit"] === "") delete i["unit"];
      if (i["category"] === null || i["category"] === "") delete i["category"];
      return i;
    });
  }

  for (const key of ["servings", "prep_time", "cook_time"]) {
    const value = out[key];
    if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) out[key] = Number(value);
    if (out[key] === null || out[key] === 0 || out[key] === "") delete out[key];
  }
  for (const key of ["tags", "cook_methods", "source_text", "note"]) {
    if (out[key] === null || out[key] === "") delete out[key];
  }
  return out;
}

export const createRecipeDraft: Tool<z.infer<typeof draftSchema>> = {
  name: "create_recipe_draft",
  kind: "WRITE_DRAFT",
  description:
    "Propose a recipe. It lands in the person's review queue as a draft and reaches the cookbook only if they promote it. " +
    "Required: `title` (a short name, e.g. \"Mom's Chili\"), `ingredients` (a list of objects with name, and quantity/unit when given) " +
    "and `steps` (a list of strings, in order). There is no description field: put the person's own words in `source_text`. " +
    "Use only details the person actually gave; ask instead of inventing missing quantities, times or steps.",
  schema: z.preprocess(normaliseDraftArguments, draftSchema) as unknown as z.ZodType<z.infer<typeof draftSchema>>,
  label: (args) => `Drafting “${args.title}”…`,
  async execute(args, ctx) {
    const payload = {
      title: args.title,
      source_type: "manual",
      cook_methods: args.cook_methods ?? [],
      tags: args.tags ?? [],
      is_favorite: false,
      ...(args.prep_time !== undefined ? { prep_time: args.prep_time } : {}),
      ...(args.cook_time !== undefined ? { cook_time: args.cook_time } : {}),
      ...(args.servings !== undefined ? { servings: args.servings } : {}),
      ingredients: args.ingredients.map((i) => ({
        name: i.name,
        quantity: i.quantity ?? null,
        unit: i.unit ?? null,
        category: i.category ?? "misc",
      })),
      // Step numbers are assigned by position, so a proposed draft cannot trip
      // validation's 1..n sequence check on the model's account.
      steps: args.steps.map((text, index) => ({ order: index + 1, instruction_text: text })),
      alternates: [],
    };
    const draft = await ctx.cookvault.post<AgentDraft>("/agent/recipe-drafts", {
      title: args.title,
      payload,
      provenance: {
        source_type: "manual",
        ...(args.source_text ? { original_text: args.source_text } : {}),
        agent_model: ctx.model,
        agent_version: ctx.version,
      },
      ...(args.note ? { note: args.note } : {}),
    });
    return {
      content: {
        draft_id: draft.id,
        status: draft.status,
        valid: draft.valid,
        issues: draft.issues.map((i) => `${i.severity}: ${i.field} — ${i.message}`),
        reminder: "This is a draft in the review queue. It is not saved to the cookbook until the person promotes it.",
      },
      summary: draft.valid ? "draft ready for review" : "draft needs attention",
      links: [{ kind: "draft", id: draft.id, title: draft.title ?? args.title }],
      affectedId: draft.id,
    };
  },
};

const planDraftSchema = z.object({
  title: z.string().max(255).optional().describe('e.g. "Week of 2026-03-01".'),
  meals: z
    .array(
      z.object({
        date: isoDate,
        recipe_id: z.string().uuid().describe("An id from suggest_meal_plan or search_recipes."),
        meal_type: z.enum(["breakfast", "lunch", "dinner", "snack"]).optional(),
        servings: z.number().int().positive().optional(),
        reason: z.string().optional().describe("Why this recipe on this day. Shown to the person."),
      }),
    )
    .min(1),
  note: z.string().optional().describe("For the reviewer."),
});

type PlanDraft = { id: string; status: string; title: string | null; covers_from: string | null; covers_to: string | null };

export const createMealPlanDraft: Tool<z.infer<typeof planDraftSchema>> = {
  name: "create_meal_plan_draft",
  kind: "WRITE_DRAFT",
  description: "Propose a week of meals. Nothing is put on the calendar until the person approves it, and they can swap or drop any meal first.",
  schema: planDraftSchema,
  label: () => "Proposing a week…",
  async execute(args, ctx) {
    const draft = await ctx.cookvault.post<PlanDraft>("/agent/meal-plan-drafts", {
      ...(args.title ? { title: args.title } : {}),
      meals: args.meals.map((m) => ({
        date: m.date,
        recipe_id: m.recipe_id,
        meal_type: m.meal_type ?? "dinner",
        ...(m.servings ? { servings: m.servings } : {}),
        ...(m.reason ? { reason: m.reason } : {}),
      })),
      ...(args.note ? { note: args.note } : {}),
      agent_model: ctx.model,
      agent_version: ctx.version,
    });
    return {
      content: {
        plan_draft_id: draft.id,
        status: draft.status,
        covers: `${draft.covers_from ?? "?"} to ${draft.covers_to ?? "?"}`,
        reminder: "This is a proposal. It is not on the calendar until the person approves it.",
      },
      summary: `${args.meals.length} meals proposed`,
      links: [{ kind: "proposal", id: draft.id, title: draft.title ?? "Proposed week" }],
      affectedId: draft.id,
    };
  },
};

export function defaultRegistry(): ToolRegistry {
  return new ToolRegistry()
    .register(searchRecipes)
    .register(getRecipe)
    .register(getMealPlan)
    .register(suggestMealPlan)
    .register(parseRecipeSource)
    .register(createRecipeDraft)
    .register(createMealPlanDraft);
}
