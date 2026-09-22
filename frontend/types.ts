export type IngredientCategory = "raw_ingredient" | "spice_sauce" | "pantry_dry_good" | "misc";
export type SourceType = "manual" | "youtube" | "tiktok" | "instagram" | "web";
export type AlternateType = "cook_method" | "ingredient_substitute";
export type MealPlanMode = "auto" | "manual";

export interface Ingredient {
  id: string;
  recipe_id: string;
  position: number;
  name: string;
  /** Decimal from the API, serialized as a string (e.g. "1.500"). */
  quantity: string | null;
  unit: string | null;
  category: IngredientCategory;
}

export interface Step {
  id: string;
  recipe_id: string;
  order: number;
  instruction_text: string;
  temperature: string | null;
  duration: string | null;
  notes: string | null;
}

export interface Alternate {
  id: string;
  recipe_id: string;
  type: AlternateType;
  original_value: string;
  alternate_value: string;
  notes: string | null;
}

export interface RecipeSummary {
  id: string;
  title: string;
  source_type: SourceType;
  source_url: string | null;
  cook_methods: string[];
  prep_time: number | null;
  cook_time: number | null;
  servings: number | null;
  /** Decimal from the API, serialized as a string (e.g. "9.99"). */
  estimated_cost: string | null;
  tags: string[];
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

export interface RecipeDetail extends RecipeSummary {
  ingredients: Ingredient[];
  steps: Step[];
  alternates: Alternate[];
  /** Set when the response was scaled at read time; the stored recipe is
   *  always canonical. Null means "as written". */
  scaled_to_servings: number | null;
  applied_scale: string | null;
}

export type MealType = "breakfast" | "lunch" | "dinner" | "snack";

export interface ShoppingListItem {
  id: string;
  recipe_id: string | null;
  name: string;
  /** Decimal from the API, serialized as a string (e.g. "1.500"). */
  quantity: string | null;
  unit: string | null;
  category: IngredientCategory;
  is_checked: boolean;
  /** True for rows built by "generate from recipes"; those are replaced on
   *  the next generate, while hand-added items survive it. */
  is_generated: boolean;
}

export interface RecipeFacets {
  tags: string[];
  cook_methods: string[];
}

export interface MealPlanEntry {
  id: string;
  date: string;
  recipe_id: string;
  mode: MealPlanMode;
  meal_type: MealType | null;
  /** Servings wanted on the day; null means "as the recipe is written". */
  servings: number | null;
}
