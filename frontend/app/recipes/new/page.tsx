"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { apiFetch } from "@/lib/api";
import type { IngredientCategory } from "@/types";

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

const emptyIngredient = (category: IngredientCategory): DraftIngredient => ({
  name: "",
  quantity: "",
  unit: "",
  category,
});

const COLUMNS: { category: IngredientCategory; label: string }[] = [
  { category: "raw_ingredient", label: "Raw Ingredients" },
  { category: "spice_sauce", label: "Spices & Sauces" },
  { category: "pantry_dry_good", label: "Pantry & Dry Goods" },
  { category: "misc", label: "Misc" },
];

export default function NewRecipePage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [prepTime, setPrepTime] = useState("");
  const [cookTime, setCookTime] = useState("");
  const [servings, setServings] = useState("");
  const [ingredients, setIngredients] = useState<DraftIngredient[]>([emptyIngredient("raw_ingredient")]);
  const [steps, setSteps] = useState<DraftStep[]>([{ instruction_text: "", temperature: "", duration: "", notes: "" }]);
  const [importUrl, setImportUrl] = useState("");
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function updateIngredient(index: number, patch: Partial<DraftIngredient>) {
    setIngredients((prev) => prev.map((ing, i) => (i === index ? { ...ing, ...patch } : ing)));
  }

  function addIngredient(category: IngredientCategory) {
    setIngredients((prev) => [...prev, emptyIngredient(category)]);
  }

  function removeIngredient(index: number) {
    setIngredients((prev) => prev.filter((_, i) => i !== index));
  }

  function updateStep(index: number, patch: Partial<DraftStep>) {
    setSteps((prev) => prev.map((step, i) => (i === index ? { ...step, ...patch } : step)));
  }

  function addStep() {
    setSteps((prev) => [...prev, { instruction_text: "", temperature: "", duration: "", notes: "" }]);
  }

  function removeStep(index: number) {
    setSteps((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleImport(e: React.FormEvent) {
    e.preventDefault();
    setImportMessage(null);
    try {
      await apiFetch("/import", { method: "POST", body: JSON.stringify({ url: importUrl }) });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Import failed";
      if (message.includes("501")) {
        setImportMessage(
          "Import from a link isn't built yet — that's a Phase 2 feature. Enter the recipe manually below for now."
        );
      } else {
        setImportMessage(message);
      }
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const payload = {
        title,
        prep_time: prepTime ? Number(prepTime) : null,
        cook_time: cookTime ? Number(cookTime) : null,
        servings: servings ? Number(servings) : null,
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
      };
      const created = await apiFetch<{ id: string }>("/recipes", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      router.push(`/recipes/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save recipe");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-10">
      <section>
        <h1 className="mb-4 text-xl font-semibold">Import from a link</h1>
        <form onSubmit={handleImport} className="flex gap-2">
          <input
            type="url"
            placeholder="YouTube, TikTok, Instagram, or web URL"
            value={importUrl}
            onChange={(e) => setImportUrl(e.target.value)}
            className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm"
          />
          <button type="submit" className="rounded bg-neutral-800 px-4 py-2 text-sm text-white">
            Import
          </button>
        </form>
        {importMessage && <p className="mt-2 text-sm text-amber-600">{importMessage}</p>}
      </section>

      <hr className="border-neutral-200" />

      <form onSubmit={handleSubmit} className="space-y-8">
        <h1 className="text-xl font-semibold">Add Recipe Manually</h1>

        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <input
            placeholder="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            className="col-span-2 rounded border border-neutral-300 px-3 py-2 text-sm md:col-span-4"
          />
          <input
            placeholder="Prep time (min)"
            value={prepTime}
            onChange={(e) => setPrepTime(e.target.value)}
            className="rounded border border-neutral-300 px-3 py-2 text-sm"
          />
          <input
            placeholder="Cook time (min)"
            value={cookTime}
            onChange={(e) => setCookTime(e.target.value)}
            className="rounded border border-neutral-300 px-3 py-2 text-sm"
          />
          <input
            placeholder="Servings"
            value={servings}
            onChange={(e) => setServings(e.target.value)}
            className="rounded border border-neutral-300 px-3 py-2 text-sm"
          />
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
                        className="w-12 rounded border border-neutral-300 px-1 py-1 text-xs"
                      />
                      <input
                        placeholder="unit"
                        value={ing.unit}
                        onChange={(e) => updateIngredient(idx, { unit: e.target.value })}
                        className="w-14 rounded border border-neutral-300 px-1 py-1 text-xs"
                      />
                      <input
                        placeholder="name"
                        value={ing.name}
                        onChange={(e) => updateIngredient(idx, { name: e.target.value })}
                        className="flex-1 rounded border border-neutral-300 px-1 py-1 text-xs"
                      />
                      <button type="button" onClick={() => removeIngredient(idx)} className="text-xs text-neutral-400">
                        ✕
                      </button>
                    </div>
                  ))}
                <button
                  type="button"
                  onClick={() => addIngredient(column.category)}
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
                  <button type="button" onClick={() => removeStep(idx)} className="mt-2 text-xs text-neutral-400">
                    ✕
                  </button>
                </div>
                <div className="ml-6 flex gap-2">
                  <input
                    placeholder="Temp"
                    value={step.temperature}
                    onChange={(e) => updateStep(idx, { temperature: e.target.value })}
                    className="w-24 rounded border border-neutral-300 px-2 py-1 text-xs"
                  />
                  <input
                    placeholder="Duration"
                    value={step.duration}
                    onChange={(e) => updateStep(idx, { duration: e.target.value })}
                    className="w-24 rounded border border-neutral-300 px-2 py-1 text-xs"
                  />
                  <input
                    placeholder="Notes"
                    value={step.notes}
                    onChange={(e) => updateStep(idx, { notes: e.target.value })}
                    className="flex-1 rounded border border-neutral-300 px-2 py-1 text-xs"
                  />
                </div>
              </div>
            ))}
            <button type="button" onClick={addStep} className="text-xs text-neutral-500 underline">
              + add step
            </button>
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-neutral-800 px-6 py-2 text-sm text-white disabled:opacity-50"
        >
          {submitting ? "Saving…" : "Save Recipe"}
        </button>
      </form>
    </div>
  );
}
