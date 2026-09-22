"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { IngredientColumn } from "@/components/IngredientColumn";
import { StepList } from "@/components/StepList";
import { apiFetch } from "@/lib/api";
import { formatCost } from "@/lib/format";
import type { IngredientCategory, RecipeDetail as RecipeDetailType } from "@/types";

const COLUMNS: { category: IngredientCategory; label: string }[] = [
  { category: "raw_ingredient", label: "Raw Ingredients" },
  { category: "spice_sauce", label: "Spices & Sauces" },
  { category: "pantry_dry_good", label: "Pantry & Dry Goods" },
  { category: "misc", label: "Misc" },
];

export default function RecipeDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [recipe, setRecipe] = useState<RecipeDetailType | null>(null);
  // Null means "as written". Scaling is a read-time transform: the server
  // returns scaled quantities and the stored recipe never changes.
  const [servings, setServings] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const query = servings === null ? "" : `?servings=${servings}`;
    apiFetch<RecipeDetailType>(`/recipes/${params.id}${query}`)
      .then(setRecipe)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load recipe"));
  }, [params.id, servings]);

  async function toggleFavorite() {
    if (!recipe) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await apiFetch<RecipeDetailType>(`/recipes/${recipe.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_favorite: !recipe.is_favorite }),
      });
      setRecipe(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update favorite");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!recipe) return;
    if (!window.confirm(`Delete “${recipe.title}”? This can't be undone.`)) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/recipes/${recipe.id}`, { method: "DELETE" });
      router.push("/library");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete recipe");
      setBusy(false);
    }
  }

  if (error && !recipe) return <p className="text-sm text-red-600">{error}</p>;
  if (!recipe) return <p className="text-neutral-500">Loading…</p>;

  const byCategory = (category: IngredientCategory) =>
    recipe.ingredients.filter((i) => i.category === category);

  // A recipe that never recorded its own yield has no baseline to scale from.
  const canScale = (recipe.scaled_to_servings ?? recipe.servings ?? 0) > 0;
  const baseServings = recipe.scaled_to_servings
    ? Math.round(recipe.scaled_to_servings / Number(recipe.applied_scale ?? 1))
    : recipe.servings;
  const isScaled = recipe.scaled_to_servings !== null;

  const meta = [
    recipe.prep_time ? `${recipe.prep_time}m prep` : null,
    recipe.cook_time ? `${recipe.cook_time}m cook` : null,
    recipe.servings ? `serves ${recipe.servings}` : null,
    formatCost(recipe.estimated_cost) ? `~${formatCost(recipe.estimated_cost)}` : null,
    recipe.cook_methods.length > 0 ? recipe.cook_methods.join(", ") : null,
  ].filter(Boolean);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{recipe.title}</h1>
          {meta.length > 0 && <p className="mt-1 text-sm text-neutral-500">{meta.join(" · ")}</p>}
          {recipe.tags.length > 0 && (
            <p className="mt-2 text-xs text-neutral-400">{recipe.tags.join(" · ")}</p>
          )}
          {recipe.source_url && (
            <a
              href={recipe.source_url}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-block text-xs text-neutral-500 underline"
            >
              Source
            </a>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleFavorite}
            disabled={busy}
            aria-pressed={recipe.is_favorite}
            className="rounded border border-neutral-300 px-3 py-1 text-sm disabled:opacity-50"
          >
            {recipe.is_favorite ? "★ Favorite" : "☆ Favorite"}
          </button>
          <Link
            href={`/recipes/${recipe.id}/edit`}
            className="rounded border border-neutral-300 px-3 py-1 text-sm"
          >
            Edit
          </Link>
          <button
            onClick={handleDelete}
            disabled={busy}
            className="rounded border border-red-300 px-3 py-1 text-sm text-red-600 disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex flex-wrap items-center gap-2 rounded border border-neutral-200 p-3">
        <span className="text-sm font-medium">Make for</span>
        {canScale ? (
          <>
            {[0.5, 1, 1.5, 2].map((multiplier) => {
              const target = Math.round((baseServings ?? 0) * multiplier);
              const active = (recipe.scaled_to_servings ?? recipe.servings) === target;
              return (
                <button
                  key={multiplier}
                  onClick={() => setServings(multiplier === 1 ? null : target)}
                  className={`rounded border px-3 py-1 text-sm ${
                    active ? "border-neutral-800 bg-neutral-800 text-white" : "border-neutral-300"
                  }`}
                >
                  {multiplier}×
                </button>
              );
            })}
            <input
              type="number"
              min={1}
              aria-label="Servings"
              value={recipe.scaled_to_servings ?? recipe.servings ?? ""}
              onChange={(e) => {
                const value = Number(e.target.value);
                setServings(Number.isFinite(value) && value > 0 ? value : null);
              }}
              className="w-20 rounded border border-neutral-300 px-2 py-1 text-sm"
            />
            <span className="text-sm text-neutral-500">servings</span>
            {isScaled && (
              <span className="text-xs text-neutral-500">
                scaled {recipe.applied_scale}× from {baseServings} — the saved recipe is unchanged
              </span>
            )}
          </>
        ) : (
          <span className="text-sm text-neutral-500">
            Set a servings count on this recipe to scale it.
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
        {COLUMNS.map((column) => (
          <IngredientColumn
            key={column.category}
            title={column.label}
            ingredients={byCategory(column.category)}
          />
        ))}
      </div>

      <hr className="border-neutral-200" />

      <div>
        <h2 className="mb-4 text-lg font-semibold">Steps</h2>
        <StepList steps={recipe.steps} />
      </div>

      <div>
        <h2 className="mb-4 text-lg font-semibold">Alternates</h2>
        {recipe.alternates.length === 0 ? (
          <p className="text-neutral-500">No alternates recorded.</p>
        ) : (
          <ul className="space-y-2">
            {recipe.alternates.map((alt) => (
              <li key={alt.id} className="text-sm">
                <span className="text-xs uppercase tracking-wide text-neutral-400">
                  {alt.type === "cook_method" ? "method" : "ingredient"}
                </span>{" "}
                <span className="font-medium">{alt.original_value}</span> → {alt.alternate_value}
                {alt.notes && <span className="text-neutral-400"> ({alt.notes})</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
