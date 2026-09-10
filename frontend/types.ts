export type IngredientCategory = "raw_ingredient" | "spice_sauce" | "pantry_dry_good" | "misc";
export type SourceType = "manual" | "youtube" | "tiktok" | "instagram" | "web";
export type AlternateType = "cook_method" | "ingredient_substitute";
export type MealPlanMode = "auto" | "manual";

export interface Ingredient {
  id: string;
  recipe_id: string;
  name: string;
  quantity: number | null;
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
  estimated_cost: number | null;
  tags: string[];
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

export interface RecipeDetail extends RecipeSummary {
  ingredients: Ingredient[];
  steps: Step[];
  alternates: Alternate[];
}

export interface ShoppingListItem {
  id: string;
  recipe_id: string | null;
  name: string;
  quantity: number | null;
  unit: string | null;
  category: IngredientCategory;
  is_checked: boolean;
}

export interface MealPlanEntry {
  id: string;
  date: string;
  recipe_id: string;
  mode: MealPlanMode;
}
