import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";
import { useState } from "react";

import { ErrorText } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { COLUMNS } from "@/lib/recipes";
import type { AlternateType, IngredientCategory } from "@/types";

interface DraftIngredient {
  name: string;
  quantity: string;
  unit: string;
  category: IngredientCategory;
}

interface DraftStep {
  instruction_text: string;
  temperature: string;
  duration: string;
  notes: string;
}

interface DraftAlternate {
  type: AlternateType;
  original_value: string;
  alternate_value: string;
  notes: string;
}

/** What the form can be seeded from.
 *
 * A `RecipeDetail` satisfies this, and so does a draft's payload -- which may
 * be missing most of its fields, because a draft is allowed to be half-formed.
 * Hence every field optional and every read defended.
 */
export interface RecipeFormInitial {
  title?: string | null;
  source_url?: string | null;
  cook_methods?: string[] | null;
  prep_time?: number | null;
  cook_time?: number | null;
  servings?: number | null;
  estimated_cost?: number | string | null;
  tags?: string[] | null;
  is_favorite?: boolean | null;
  ingredients?:
    | {
        name?: string | null;
        quantity?: number | string | null;
        unit?: string | null;
        category?: IngredientCategory | null;
      }[]
    | null;
  steps?:
    | {
        order?: number | null;
        instruction_text?: string | null;
        temperature?: string | null;
        duration?: string | null;
        notes?: string | null;
      }[]
    | null;
  alternates?:
    | {
        type?: AlternateType | null;
        original_value?: string | null;
        alternate_value?: string | null;
        notes?: string | null;
      }[]
    | null;
}

export interface RecipePayload {
  title: string;
  source_url: string | null;
  cook_methods: string[];
  prep_time: number | null;
  cook_time: number | null;
  servings: number | null;
  estimated_cost: number | null;
  tags: string[];
  is_favorite: boolean;
  ingredients: { name: string; quantity: number | null; unit: string | null; category: IngredientCategory }[];
  steps: {
    order: number;
    instruction_text: string;
    temperature: string | null;
    duration: string | null;
    notes: string | null;
  }[];
  alternates: { type: AlternateType; original_value: string; alternate_value: string; notes: string | null }[];
}

const emptyIngredient = (category: IngredientCategory): DraftIngredient => ({ name: "", quantity: "", unit: "", category });
const emptyStep = (): DraftStep => ({ instruction_text: "", temperature: "", duration: "", notes: "" });
const emptyAlternate = (): DraftAlternate => ({ type: "ingredient_substitute", original_value: "", alternate_value: "", notes: "" });

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

/** The one recipe form: new recipe, edit recipe, and draft review all use it,
 *  so the four-column layout is the same everywhere a recipe is typed. */
export function RecipeForm({
  initial,
  submitLabel,
  onSubmit,
}: {
  initial?: RecipeFormInitial;
  submitLabel: string;
  onSubmit: (payload: RecipePayload) => Promise<void>;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [prepTime, setPrepTime] = useState(initial?.prep_time?.toString() ?? "");
  const [cookTime, setCookTime] = useState(initial?.cook_time?.toString() ?? "");
  const [servings, setServings] = useState(initial?.servings?.toString() ?? "");
  const [estimatedCost, setEstimatedCost] = useState(initial?.estimated_cost?.toString() ?? "");
  const [sourceUrl, setSourceUrl] = useState(initial?.source_url ?? "");
  const [tags, setTags] = useState(initial?.tags?.join(", ") ?? "");
  const [cookMethods, setCookMethods] = useState(initial?.cook_methods?.join(", ") ?? "");
  const [isFavorite, setIsFavorite] = useState(initial?.is_favorite ?? false);

  const [ingredients, setIngredients] = useState<DraftIngredient[]>(
    initial?.ingredients && initial.ingredients.length > 0
      ? initial.ingredients.map((i) => ({
          name: i.name ?? "",
          quantity: i.quantity?.toString() ?? "",
          unit: i.unit ?? "",
          category: i.category ?? "misc",
        }))
      : [emptyIngredient("raw_ingredient")],
  );
  const [steps, setSteps] = useState<DraftStep[]>(
    initial?.steps && initial.steps.length > 0
      ? [...initial.steps]
          .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
          .map((s) => ({
            instruction_text: s.instruction_text ?? "",
            temperature: s.temperature ?? "",
            duration: s.duration ?? "",
            notes: s.notes ?? "",
          }))
      : [emptyStep()],
  );
  const [alternates, setAlternates] = useState<DraftAlternate[]>(
    initial?.alternates?.map((a) => ({
      type: a.type ?? "ingredient_substitute",
      original_value: a.original_value ?? "",
      alternate_value: a.alternate_value ?? "",
      notes: a.notes ?? "",
    })) ?? [],
  );

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const updateIngredient = (index: number, patch: Partial<DraftIngredient>) =>
    setIngredients((prev) => prev.map((ing, i) => (i === index ? { ...ing, ...patch } : ing)));
  const updateStep = (index: number, patch: Partial<DraftStep>) =>
    setSteps((prev) => prev.map((step, i) => (i === index ? { ...step, ...patch } : step)));
  const updateAlternate = (index: number, patch: Partial<DraftAlternate>) =>
    setAlternates((prev) => prev.map((alt, i) => (i === index ? { ...alt, ...patch } : alt)));

  function moveStep(index: number, delta: number) {
    setSteps((prev) => {
      const target = index + delta;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      const a = next[index];
      const b = next[target];
      if (!a || !b) return prev;
      next[index] = b;
      next[target] = a;
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await onSubmit({
        title,
        source_url: sourceUrl.trim() || null,
        cook_methods: splitList(cookMethods),
        prep_time: prepTime ? Number(prepTime) : null,
        cook_time: cookTime ? Number(cookTime) : null,
        servings: servings ? Number(servings) : null,
        estimated_cost: estimatedCost ? Number(estimatedCost) : null,
        tags: splitList(tags),
        is_favorite: isFavorite,
        ingredients: ingredients
          .filter((i) => i.name.trim())
          .map((i) => ({
            name: i.name,
            quantity: i.quantity ? Number(i.quantity) : null,
            unit: i.unit || null,
            category: i.category,
          })),
        steps: steps
          .filter((s) => s.instruction_text.trim())
          .map((s, idx) => ({
            order: idx + 1,
            instruction_text: s.instruction_text,
            temperature: s.temperature || null,
            duration: s.duration || null,
            notes: s.notes || null,
          })),
        alternates: alternates
          .filter((a) => a.original_value.trim() && a.alternate_value.trim())
          .map((a) => ({
            type: a.type,
            original_value: a.original_value,
            alternate_value: a.alternate_value,
            notes: a.notes || null,
          })),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save recipe");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <section className="glass-panel editor-form">
        <label>
          Recipe name
          <input className="field" value={title} onChange={(e) => setTitle(e.target.value)} required placeholder="Grandma's tomato soup" />
        </label>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <label>
            Prep (min)
            <input className="field" inputMode="numeric" value={prepTime} onChange={(e) => setPrepTime(e.target.value)} />
          </label>
          <label>
            Cook (min)
            <input className="field" inputMode="numeric" value={cookTime} onChange={(e) => setCookTime(e.target.value)} />
          </label>
          <label>
            Servings
            <input className="field" inputMode="numeric" value={servings} onChange={(e) => setServings(e.target.value)} />
          </label>
          <label>
            Est. cost ($)
            <input className="field" inputMode="decimal" value={estimatedCost} onChange={(e) => setEstimatedCost(e.target.value)} />
          </label>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label>
            Tags, comma separated
            <input className="field" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="italian, weeknight" />
          </label>
          <label>
            Cook methods
            <input className="field" value={cookMethods} onChange={(e) => setCookMethods(e.target.value)} placeholder="stovetop, oven" />
          </label>
        </div>
        <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
          <label>
            Source URL (optional)
            <input className="field" type="url" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} />
          </label>
          <label className="!flex items-center gap-2 pb-2">
            <input type="checkbox" checked={isFavorite} onChange={(e) => setIsFavorite(e.target.checked)} className="size-4 accent-[oklch(0.72_0.17_160)]" />
            Favorite
          </label>
        </div>
      </section>

      <section className="glass-panel p-6">
        <h2 className="mb-4 font-display text-2xl font-semibold">Ingredients</h2>
        <div className="columns-4">
          {COLUMNS.map((column) => (
            <div key={column.category} className="column">
              <h3>{column.label}</h3>
              <div className="space-y-2">
                {ingredients
                  .map((ing, idx) => ({ ing, idx }))
                  .filter(({ ing }) => ing.category === column.category)
                  .map(({ ing, idx }) => (
                    <div key={idx} className="flex gap-1">
                      <input
                        placeholder="qty"
                        aria-label="Quantity"
                        value={ing.quantity}
                        onChange={(e) => updateIngredient(idx, { quantity: e.target.value })}
                        className="field field-sm w-14 shrink-0 !px-1.5"
                      />
                      <input
                        placeholder="unit"
                        aria-label="Unit"
                        value={ing.unit}
                        onChange={(e) => updateIngredient(idx, { unit: e.target.value })}
                        className="field field-sm w-16 shrink-0 !px-1.5"
                      />
                      <input
                        placeholder="name"
                        aria-label="Ingredient"
                        value={ing.name}
                        onChange={(e) => updateIngredient(idx, { name: e.target.value })}
                        className="field field-sm min-w-0 flex-1"
                      />
                      <button
                        type="button"
                        aria-label={`Remove ${ing.name || "ingredient"}`}
                        onClick={() => setIngredients((prev) => prev.filter((_, i) => i !== idx))}
                        className="text-muted-foreground/60 hover:text-destructive"
                      >
                        <X className="size-4" />
                      </button>
                    </div>
                  ))}
                <button
                  type="button"
                  onClick={() => setIngredients((prev) => [...prev, emptyIngredient(column.category)])}
                  className="inline-flex items-center gap-1 text-xs font-semibold text-primary"
                >
                  <Plus className="size-3.5" /> add
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="glass-panel p-6">
        <h2 className="mb-4 font-display text-2xl font-semibold">Method</h2>
        <div className="space-y-3">
          {steps.map((step, idx) => (
            <div key={idx} className="rounded-xl border border-border bg-white/40 p-3">
              <div className="flex items-start gap-2">
                <span className="step-number">{idx + 1}</span>
                <textarea
                  placeholder="Instruction"
                  aria-label={`Step ${idx + 1}`}
                  value={step.instruction_text}
                  onChange={(e) => updateStep(idx, { instruction_text: e.target.value })}
                  className="field !min-h-16 flex-1"
                />
                <div className="flex flex-col gap-1 text-muted-foreground">
                  <button type="button" aria-label="Move step up" onClick={() => moveStep(idx, -1)} className="hover:text-foreground">
                    <ArrowUp className="size-4" />
                  </button>
                  <button type="button" aria-label="Move step down" onClick={() => moveStep(idx, 1)} className="hover:text-foreground">
                    <ArrowDown className="size-4" />
                  </button>
                  <button
                    type="button"
                    aria-label="Remove step"
                    onClick={() => setSteps((prev) => prev.filter((_, i) => i !== idx))}
                    className="hover:text-destructive"
                  >
                    <X className="size-4" />
                  </button>
                </div>
              </div>
              <div className="ml-9 mt-2 flex flex-wrap gap-2">
                <input placeholder="Temp" aria-label="Temperature" value={step.temperature} onChange={(e) => updateStep(idx, { temperature: e.target.value })} className="field field-sm w-28" />
                <input placeholder="Duration" aria-label="Duration" value={step.duration} onChange={(e) => updateStep(idx, { duration: e.target.value })} className="field field-sm w-28" />
                <input placeholder="Notes" aria-label="Step notes" value={step.notes} onChange={(e) => updateStep(idx, { notes: e.target.value })} className="field field-sm min-w-40 flex-1" />
              </div>
            </div>
          ))}
          <button type="button" onClick={() => setSteps((prev) => [...prev, emptyStep()])} className="inline-flex items-center gap-1 text-xs font-semibold text-primary">
            <Plus className="size-3.5" /> add step
          </button>
        </div>
      </section>

      <section className="glass-panel p-6">
        <h2 className="mb-1 font-display text-2xl font-semibold">Alternates</h2>
        <p className="mb-4 text-sm text-muted-foreground">Swaps that still work: another cut, another cooker.</p>
        <div className="space-y-2">
          {alternates.map((alt, idx) => (
            <div key={idx} className="flex flex-wrap items-center gap-2">
              <select value={alt.type} onChange={(e) => updateAlternate(idx, { type: e.target.value as AlternateType })} aria-label="Alternate type" className="field field-sm w-36">
                <option value="ingredient_substitute">ingredient</option>
                <option value="cook_method">cook method</option>
              </select>
              <input placeholder="instead of" aria-label="Original" value={alt.original_value} onChange={(e) => updateAlternate(idx, { original_value: e.target.value })} className="field field-sm w-36" />
              <span className="text-xs text-muted-foreground">→</span>
              <input placeholder="use" aria-label="Alternate" value={alt.alternate_value} onChange={(e) => updateAlternate(idx, { alternate_value: e.target.value })} className="field field-sm w-36" />
              <input placeholder="notes" aria-label="Alternate notes" value={alt.notes} onChange={(e) => updateAlternate(idx, { notes: e.target.value })} className="field field-sm min-w-40 flex-1" />
              <button type="button" aria-label="Remove alternate" onClick={() => setAlternates((prev) => prev.filter((_, i) => i !== idx))} className="text-muted-foreground/60 hover:text-destructive">
                <X className="size-4" />
              </button>
            </div>
          ))}
          <button type="button" onClick={() => setAlternates((prev) => [...prev, emptyAlternate()])} className="inline-flex items-center gap-1 text-xs font-semibold text-primary">
            <Plus className="size-3.5" /> add alternate
          </button>
        </div>
      </section>

      <ErrorText>{error}</ErrorText>

      <div className="flex justify-end">
        <Button type="submit" size="lg" disabled={submitting} className="rounded-xl">
          {submitting ? "Saving…" : submitLabel}
        </Button>
      </div>
    </form>
  );
}
