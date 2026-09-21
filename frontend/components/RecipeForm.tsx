"use client";

import { useState } from "react";

import type { AlternateType, IngredientCategory, RecipeDetail } from "@/types";

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
  ingredients: {
    name: string;
    quantity: number | null;
    unit: string | null;
    category: IngredientCategory;
  }[];
  steps: {
    order: number;
    instruction_text: string;
    temperature: string | null;
    duration: string | null;
    notes: string | null;
  }[];
  alternates: {
    type: AlternateType;
    original_value: string;
    alternate_value: string;
    notes: string | null;
  }[];
}

const COLUMNS: { category: IngredientCategory; label: string }[] = [
  { category: "raw_ingredient", label: "Raw Ingredients" },
  { category: "spice_sauce", label: "Spices & Sauces" },
  { category: "pantry_dry_good", label: "Pantry & Dry Goods" },
  { category: "misc", label: "Misc" },
];

const emptyIngredient = (category: IngredientCategory): DraftIngredient => ({
  name: "",
  quantity: "",
  unit: "",
  category,
});

const emptyStep = (): DraftStep => ({ instruction_text: "", temperature: "", duration: "", notes: "" });

const emptyAlternate = (): DraftAlternate => ({
  type: "ingredient_substitute",
  original_value: "",
  alternate_value: "",
  notes: "",
});

const textInput = "rounded border border-neutral-300 px-3 py-2 text-sm";
const tinyInput = "rounded border border-neutral-300 px-1 py-1 text-xs";

export function RecipeForm({
  initial,
  submitLabel,
  onSubmit,
}: {
  initial?: RecipeDetail;
  submitLabel: string;
  onSubmit: (payload: RecipePayload) => Promise<void>;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [prepTime, setPrepTime] = useState(initial?.prep_time?.toString() ?? "");
  const [cookTime, setCookTime] = useState(initial?.cook_time?.toString() ?? "");
  const [servings, setServings] = useState(initial?.servings?.toString() ?? "");
  const [estimatedCost, setEstimatedCost] = useState(initial?.estimated_cost?.toString() ?? "");
  const [sourceUrl, setSourceUrl] = useState(initial?.source_url ?? "");
  const [tags, setTags] = useState(initial?.tags.join(", ") ?? "");
  const [cookMethods, setCookMethods] = useState(initial?.cook_methods.join(", ") ?? "");
  const [isFavorite, setIsFavorite] = useState(initial?.is_favorite ?? false);

  const [ingredients, setIngredients] = useState<DraftIngredient[]>(
    initial && initial.ingredients.length > 0
      ? initial.ingredients.map((i) => ({
          name: i.name,
          quantity: i.quantity?.toString() ?? "",
          unit: i.unit ?? "",
          category: i.category,
        }))
      : [emptyIngredient("raw_ingredient")],
  );
  const [steps, setSteps] = useState<DraftStep[]>(
    initial && initial.steps.length > 0
      ? [...initial.steps]
          .sort((a, b) => a.order - b.order)
          .map((s) => ({
            instruction_text: s.instruction_text,
            temperature: s.temperature ?? "",
            duration: s.duration ?? "",
            notes: s.notes ?? "",
          }))
      : [emptyStep()],
  );
  const [alternates, setAlternates] = useState<DraftAlternate[]>(
    initial?.alternates.map((a) => ({
      type: a.type,
      original_value: a.original_value,
      alternate_value: a.alternate_value,
      notes: a.notes ?? "",
    })) ?? [],
  );

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function updateIngredient(index: number, patch: Partial<DraftIngredient>) {
    setIngredients((prev) => prev.map((ing, i) => (i === index ? { ...ing, ...patch } : ing)));
  }

  function updateStep(index: number, patch: Partial<DraftStep>) {
    setSteps((prev) => prev.map((step, i) => (i === index ? { ...step, ...patch } : step)));
  }

  function moveStep(index: number, delta: number) {
    setSteps((prev) => {
      const target = index + delta;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function updateAlternate(index: number, patch: Partial<DraftAlternate>) {
    setAlternates((prev) => prev.map((alt, i) => (i === index ? { ...alt, ...patch } : alt)));
  }

  function splitList(value: string): string[] {
    return value
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean);
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
    <form onSubmit={handleSubmit} className="space-y-8">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <input
          placeholder="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          className={`col-span-2 md:col-span-4 ${textInput}`}
        />
        <input
          placeholder="Prep time (min)"
          inputMode="numeric"
          value={prepTime}
          onChange={(e) => setPrepTime(e.target.value)}
          className={textInput}
        />
        <input
          placeholder="Cook time (min)"
          inputMode="numeric"
          value={cookTime}
          onChange={(e) => setCookTime(e.target.value)}
          className={textInput}
        />
        <input
          placeholder="Servings"
          inputMode="numeric"
          value={servings}
          onChange={(e) => setServings(e.target.value)}
          className={textInput}
        />
        <input
          placeholder="Est. cost ($)"
          inputMode="decimal"
          value={estimatedCost}
          onChange={(e) => setEstimatedCost(e.target.value)}
          className={textInput}
        />
        <input
          placeholder="Tags, comma separated (italian, weeknight)"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          className={`col-span-2 ${textInput}`}
        />
        <input
          placeholder="Cook methods (stovetop, oven)"
          value={cookMethods}
          onChange={(e) => setCookMethods(e.target.value)}
          className={`col-span-2 ${textInput}`}
        />
        <input
          type="url"
          placeholder="Source URL (optional)"
          value={sourceUrl}
          onChange={(e) => setSourceUrl(e.target.value)}
          className={`col-span-2 md:col-span-3 ${textInput}`}
        />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={isFavorite} onChange={(e) => setIsFavorite(e.target.checked)} />
          Favorite
        </label>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-4">
        {COLUMNS.map((column) => (
          <div key={column.category}>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
              {column.label}
            </h3>
            <div className="space-y-2">
              {ingredients
                .map((ing, idx) => ({ ing, idx }))
                .filter(({ ing }) => ing.category === column.category)
                .map(({ ing, idx }) => (
                  <div key={idx} className="flex gap-1">
                    <input
                      placeholder="qty"
                      value={ing.quantity}
                      onChange={(e) => updateIngredient(idx, { quantity: e.target.value })}
                      className={`w-12 ${tinyInput}`}
                    />
                    <input
                      placeholder="unit"
                      value={ing.unit}
                      onChange={(e) => updateIngredient(idx, { unit: e.target.value })}
                      className={`w-14 ${tinyInput}`}
                    />
                    <input
                      placeholder="name"
                      value={ing.name}
                      onChange={(e) => updateIngredient(idx, { name: e.target.value })}
                      className={`flex-1 ${tinyInput}`}
                    />
                    <button
                      type="button"
                      aria-label={`Remove ${ing.name || "ingredient"}`}
                      onClick={() => setIngredients((prev) => prev.filter((_, i) => i !== idx))}
                      className="text-xs text-neutral-400 hover:text-red-600"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              <button
                type="button"
                onClick={() => setIngredients((prev) => [...prev, emptyIngredient(column.category)])}
                className="text-xs text-neutral-500 underline"
              >
                + add
              </button>
            </div>
          </div>
        ))}
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">Steps</h3>
        <div className="space-y-3">
          {steps.map((step, idx) => (
            <div key={idx} className="space-y-1 rounded border border-neutral-200 p-3">
              <div className="flex items-start gap-2">
                <span className="mt-2 text-xs text-neutral-400">{idx + 1}.</span>
                <textarea
                  placeholder="Instruction"
                  value={step.instruction_text}
                  onChange={(e) => updateStep(idx, { instruction_text: e.target.value })}
                  className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
                />
                <div className="mt-1 flex flex-col text-xs text-neutral-400">
                  <button type="button" aria-label="Move step up" onClick={() => moveStep(idx, -1)}>
                    ↑
                  </button>
                  <button type="button" aria-label="Move step down" onClick={() => moveStep(idx, 1)}>
                    ↓
                  </button>
                </div>
                <button
                  type="button"
                  aria-label="Remove step"
                  onClick={() => setSteps((prev) => prev.filter((_, i) => i !== idx))}
                  className="mt-2 text-xs text-neutral-400 hover:text-red-600"
                >
                  ✕
                </button>
              </div>
              <div className="ml-6 flex gap-2">
                <input
                  placeholder="Temp"
                  value={step.temperature}
                  onChange={(e) => updateStep(idx, { temperature: e.target.value })}
                  className={`w-24 ${tinyInput}`}
                />
                <input
                  placeholder="Duration"
                  value={step.duration}
                  onChange={(e) => updateStep(idx, { duration: e.target.value })}
                  className={`w-24 ${tinyInput}`}
                />
                <input
                  placeholder="Notes"
                  value={step.notes}
                  onChange={(e) => updateStep(idx, { notes: e.target.value })}
                  className={`flex-1 ${tinyInput}`}
                />
              </div>
            </div>
          ))}
          <button
            type="button"
            onClick={() => setSteps((prev) => [...prev, emptyStep()])}
            className="text-xs text-neutral-500 underline"
          >
            + add step
          </button>
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">Alternates</h3>
        <div className="space-y-2">
          {alternates.map((alt, idx) => (
            <div key={idx} className="flex flex-wrap items-center gap-1">
              <select
                value={alt.type}
                onChange={(e) => updateAlternate(idx, { type: e.target.value as AlternateType })}
                aria-label="Alternate type"
                className={tinyInput}
              >
                <option value="ingredient_substitute">ingredient</option>
                <option value="cook_method">cook method</option>
              </select>
              <input
                placeholder="instead of"
                value={alt.original_value}
                onChange={(e) => updateAlternate(idx, { original_value: e.target.value })}
                className={`w-32 ${tinyInput}`}
              />
              <span className="text-xs text-neutral-400">→</span>
              <input
                placeholder="use"
                value={alt.alternate_value}
                onChange={(e) => updateAlternate(idx, { alternate_value: e.target.value })}
                className={`w-32 ${tinyInput}`}
              />
              <input
                placeholder="notes"
                value={alt.notes}
                onChange={(e) => updateAlternate(idx, { notes: e.target.value })}
                className={`flex-1 ${tinyInput}`}
              />
              <button
                type="button"
                aria-label="Remove alternate"
                onClick={() => setAlternates((prev) => prev.filter((_, i) => i !== idx))}
                className="text-xs text-neutral-400 hover:text-red-600"
              >
                ✕
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => setAlternates((prev) => [...prev, emptyAlternate()])}
            className="text-xs text-neutral-500 underline"
          >
            + add alternate
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="rounded bg-neutral-800 px-6 py-2 text-sm text-white disabled:opacity-50"
      >
        {submitting ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}
