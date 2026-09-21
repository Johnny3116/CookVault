"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { RecipeForm, type RecipePayload } from "@/components/RecipeForm";
import { apiFetch } from "@/lib/api";
import type { RecipeDetail } from "@/types";

export default function EditRecipePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [recipe, setRecipe] = useState<RecipeDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<RecipeDetail>(`/recipes/${params.id}`)
      .then(setRecipe)
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load recipe"));
  }, [params.id]);

  async function handleSubmit(payload: RecipePayload) {
    // PUT replaces the recipe and all its children in one call, so the form
    // doesn't have to diff ingredients and steps against per-child endpoints.
    await apiFetch(`/recipes/${params.id}`, {
      method: "PUT",
      body: JSON.stringify({ ...payload, source_type: recipe?.source_type ?? "manual" }),
    });
    router.push(`/recipes/${params.id}`);
  }

  if (loadError) return <p className="text-sm text-red-600">{loadError}</p>;
  if (!recipe) return <p className="text-neutral-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Edit “{recipe.title}”</h1>
      <RecipeForm initial={recipe} submitLabel="Save Changes" onSubmit={handleSubmit} />
    </div>
  );
}
