import { describe, expect, test } from "bun:test";

import { defaultRegistry } from "../src/tools/index.ts";

const registry = defaultRegistry();

describe("the tool list the model is shown", () => {
  test("is exactly these, and every write is a draft", () => {
    expect(registry.names().sort()).toEqual([
      "create_meal_plan_draft",
      "create_recipe_draft",
      "get_meal_plan",
      "get_recipe",
      "parse_recipe_source",
      "search_recipes",
      "suggest_meal_plan",
    ]);
    for (const name of registry.names()) {
      expect(["READ", "WRITE_DRAFT"]).toContain(registry.get(name)!.kind);
    }
  });

  test("schemas are flat: no null unions, no titles, no defaults, refs inlined", () => {
    const keys = (node: unknown, found: string[] = []): string[] => {
      if (Array.isArray(node)) node.forEach((n) => keys(n, found));
      else if (node && typeof node === "object") {
        for (const [k, v] of Object.entries(node)) {
          found.push(k);
          keys(v, found);
        }
      }
      return found;
    };
    for (const spec of registry.specs()) {
      const text = JSON.stringify(spec.parameters);
      expect(text).not.toContain('"null"');
      expect(text).not.toContain("anyOf");
      expect(text).not.toContain("$ref");
      expect(text).not.toContain("$schema");
      expect(keys(spec.parameters)).not.toContain("title");
      expect(keys(spec.parameters)).not.toContain("default");
      expect(spec.parameters["type"]).toBe("object");
    }
  });

  test("optionality lives in `required`", () => {
    const search = registry.specs().find((s) => s.name === "search_recipes")!;
    const params = search.parameters as { properties: Record<string, unknown>; required?: string[] };
    expect(params.required ?? []).toEqual([]);
    expect(Object.keys(params.properties)).toContain("max_total_time");

    const draft = registry.specs().find((s) => s.name === "create_recipe_draft")!;
    expect((draft.parameters as { required: string[] }).required).toEqual(["title", "ingredients", "steps"]);
  });

  test("sort offers only the values CookVault accepts", () => {
    const search = registry.specs().find((s) => s.name === "search_recipes")!;
    const sort = (search.parameters as { properties: { sort: { enum: string[] } } }).properties.sort;
    expect(sort.enum).toEqual(["updated", "last_cooked", "most_cooked", "title", "cost"]);
  });
});

describe("argument validation", () => {
  test("parse_recipe_source wants exactly one of text or url", () => {
    const tool = registry.get("parse_recipe_source")!;
    expect(tool.schema.safeParse({}).success).toBe(false);
    expect(tool.schema.safeParse({ text: "x", url: "https://a.test/r" }).success).toBe(false);
    expect(tool.schema.safeParse({ text: "x" }).success).toBe(true);
  });

  test("dates must be calendar dates", () => {
    const tool = registry.get("get_meal_plan")!;
    expect(tool.schema.safeParse({ start: "next thursday" }).success).toBe(false);
    expect(tool.schema.safeParse({ start: "2026-09-24", end: "2026-09-30" }).success).toBe(true);
  });

  test("a quantity must be a number, never a phrase", () => {
    const tool = registry.get("create_recipe_draft")!;
    const bad = tool.schema.safeParse({ title: "t", ingredients: [{ name: "salt", quantity: "a pinch" }], steps: ["s"] });
    expect(bad.success).toBe(false);
  });
});

describe("normalising what a small model actually sends", () => {
  const tool = registry.get("create_recipe_draft")!;

  test("aliases are renamed, empties dropped, numeric strings read as numbers", () => {
    const parsed = tool.schema.safeParse({
      name: "Mom's Chili",
      servings: 0,
      prep_time: null,
      cook_time: "60",
      ingredients: [
        { ingredient: "ground beef", quantity: "2", unit: "lb" },
        "kidney beans",
        { name: "garlic", quantity: null, unit: "", category: "" },
      ],
      instructions: [{ text: "Brown the beef." }, "Simmer an hour."],
      tags: null,
    });

    expect(parsed.success).toBe(true);
    expect(parsed.data).toEqual({
      title: "Mom's Chili",
      cook_time: 60,
      ingredients: [{ name: "ground beef", quantity: 2, unit: "lb" }, { name: "kidney beans" }, { name: "garlic" }],
      steps: ["Brown the beef.", "Simmer an hour."],
    });
  });

  test("a stray description becomes provenance rather than being lost", () => {
    const parsed = tool.schema.safeParse({ title: "t", description: "what mom said", ingredients: [{ name: "x" }], steps: ["s"] });
    expect(parsed.success).toBe(true);
    expect(parsed.data).toEqual({ title: "t", source_text: "what mom said", ingredients: [{ name: "x" }], steps: ["s"] });
  });

  test("a recipe nested under a wrapper key is lifted", () => {
    const parsed = tool.schema.safeParse({
      recipe: { title: "Chili", ingredients: [{ name: "beef" }], steps: ["Brown it."] },
      note: "unsure about the beans",
    });
    expect(parsed.success).toBe(true);
    expect(parsed.data).toEqual({ title: "Chili", ingredients: [{ name: "beef" }], steps: ["Brown it."], note: "unsure about the beans" });
  });

  test("steps given as one numbered block are split into lines", () => {
    const parsed = tool.schema.safeParse({ title: "t", ingredients: [{ name: "x" }], steps: "1. Brown the beef.\n2. Add the rest.\n" });
    expect(parsed.success).toBe(true);
    expect((parsed.data as { steps: string[] }).steps).toEqual(["Brown the beef.", "Add the rest."]);
  });

  test("normalising never invents: no title or no steps is still refused", () => {
    expect(tool.schema.safeParse({ ingredients: [{ name: "x" }], steps: ["s"] }).success).toBe(false);
    expect(tool.schema.safeParse({ title: "t", ingredients: [{ name: "x" }], steps: [] }).success).toBe(false);
    expect(tool.schema.safeParse({ title: "t", ingredients: [], steps: ["s"] }).success).toBe(false);
  });
});
