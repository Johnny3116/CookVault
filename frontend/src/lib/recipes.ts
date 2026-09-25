import type { IngredientCategory, RecipeSummary } from "@/types";

/** The four columns of the recipe page, in display order. */
export const COLUMNS: { category: IngredientCategory; label: string }[] = [
  { category: "raw_ingredient", label: "Raw Ingredients" },
  { category: "spice_sauce", label: "Spices & Sauces" },
  { category: "pantry_dry_good", label: "Pantry & Dry Goods" },
  { category: "misc", label: "Misc" },
];

export function totalMinutes(recipe: Pick<RecipeSummary, "prep_time" | "cook_time">): number | null {
  if (recipe.prep_time === null && recipe.cook_time === null) return null;
  return (recipe.prep_time ?? 0) + (recipe.cook_time ?? 0);
}

/** "35 min" / "1 h 20 min", or null when the recipe records no time. */
export function formatMinutes(minutes: number | null): string | null {
  if (minutes === null) return null;
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`;
}

/** A recipe's "category" for the chip on its card: the first tag, or the
 *  first cook method, or nothing. Recipes don't have a single category field;
 *  tags are the nearest thing and the first one is usually the cuisine. */
export function primaryTag(recipe: Pick<RecipeSummary, "tags" | "cook_methods">): string | null {
  return recipe.tags[0] ?? recipe.cook_methods[0] ?? null;
}

// Recipes carry no photos, so each card gets a stable piece of colour and a
// glyph derived from its title. Deterministic on purpose: the same recipe
// always looks the same, which is what makes it recognisable in a grid.
const HUES = [160, 82, 225, 20, 300, 45, 190, 340];
const GLYPHS = ["🍋", "🌽", "🍜", "🥚", "🍅", "🥬", "🧄", "🍞", "🧀", "🥕", "🌶️", "🍄"];

export function artFor(title: string): { hue: number; glyph: string } {
  let hash = 0;
  for (const char of title) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return {
    hue: HUES[hash % HUES.length] ?? 160,
    glyph: GLYPHS[(hash >> 3) % GLYPHS.length] ?? "🍽️",
  };
}
