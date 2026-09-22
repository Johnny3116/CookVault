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
  provenance: Provenance | null;
}

export type MealType = "breakfast" | "lunch" | "dinner" | "snack";

export type ShoppingAisle =
  | "produce"
  | "meat_seafood"
  | "dairy_eggs"
  | "bakery"
  | "frozen"
  | "pantry"
  | "drinks"
  | "household"
  | "other";

/** Where a thing lives in the shop, in the order one is walked. A different
 *  axis from IngredientCategory, which is what a thing *is* when you cook. */
export const AISLES: { key: ShoppingAisle; label: string }[] = [
  { key: "produce", label: "Produce" },
  { key: "meat_seafood", label: "Meat & Seafood" },
  { key: "dairy_eggs", label: "Dairy & Eggs" },
  { key: "bakery", label: "Bakery" },
  { key: "frozen", label: "Frozen" },
  { key: "pantry", label: "Pantry" },
  { key: "drinks", label: "Drinks" },
  { key: "household", label: "Household" },
  { key: "other", label: "Other" },
];

export interface AisleRule {
  id: string;
  term: string;
  aisle: ShoppingAisle;
  created_at: string;
}

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
  /** Resolved per response from the aisle rules, so fixing a rule fixes every
   *  line that relied on it. */
  aisle: ShoppingAisle;
  /** Set only when overridden by hand; null means "whatever the rules say". */
  aisle_override: ShoppingAisle | null;
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

export type DraftStatus = "draft" | "ready" | "promoted" | "discarded";

export type ImportMethod = "manual" | "paste" | "url_fetch" | "agent";

export interface Provenance {
  id: string;
  draft_id: string | null;
  recipe_id: string | null;
  source_type: SourceType;
  source_url: string | null;
  source_title: string | null;
  import_method: ImportMethod;
  /** The raw source -- a transcript, a pasted block. Kept apart from
   *  extracted_payload so the two can still be compared. */
  original_text: string | null;
  /** What the extractor produced, before any human edit. */
  extracted_payload: Record<string, unknown> | null;
  agent_model: string | null;
  agent_version: string | null;
  imported_at: string;
}

export interface DraftIssue {
  /** "error" blocks promotion; "warning" is worth a look before approving. */
  severity: "error" | "warning";
  field: string;
  message: string;
}

export interface DraftValidation {
  ok: boolean;
  issues: DraftIssue[];
}

export interface RecipeDraftSummary {
  id: string;
  title: string | null;
  status: DraftStatus;
  promoted_recipe_id: string | null;
  promoted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RecipeDraftDetail extends RecipeDraftSummary {
  /** Shaped like a recipe, but not guaranteed to be one yet. */
  payload: Record<string, unknown>;
  provenance: Provenance | null;
}
