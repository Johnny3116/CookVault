"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { IngredientColumn } from "@/components/IngredientColumn";
import { StepList } from "@/components/StepList";
import { apiFetch } from "@/lib/api";
import type { RecipeDetail as RecipeDetailType } from "@/types";

export default function RecipeDetailPage() {
  const params = useParams<{ id: string }>();
  const [recipe, setRecipe] = useState<RecipeDetailType | null>(null);

  useEffect(() => {
    apiFetch<RecipeDetailType>(`/recipes/${params.id}`).then(setRecipe);
  }, [params.id]);

  if (!recipe) return <p className="text-neutral-500">Loading…</p>;

  const byCategory = (category: string) => recipe.ingredients.filter((i) => i.category === category);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">{recipe.title}</h1>
        <p className="mt-1 text-sm text-neutral-500">
          {recipe.prep_time ? `${recipe.prep_time}m prep` : ""}
          {recipe.cook_time ? ` · ${recipe.cook_time}m cook` : ""}
          {recipe.servings ? ` · serves ${recipe.servings}` : ""}
          {recipe.estimated_cost ? ` · ~$${recipe.estimated_cost}` : ""}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
        <IngredientColumn title="Raw Ingredients" ingredients={byCategory("raw_ingredient")} />
        <IngredientColumn title="Spices & Sauces" ingredients={byCategory("spice_sauce")} />
        <IngredientColumn title="Pantry & Dry Goods" ingredients={byCategory("pantry_dry_good")} />
        <IngredientColumn title="Misc" ingredients={byCategory("misc")} />
      </div>

      <hr className="border-neutral-200" />

      <div>
        <h2 className="mb-4 text-lg font-semibold">Steps</h2>
        <StepList steps={recipe.steps} />
      </div>

      <div>
        <h2 className="mb-4 text-lg font-semibold">Alternates</h2>
        {recipe.alternates.length === 0 && <p className="text-neutral-500">No alternates recorded.</p>}
        <ul className="space-y-2">
          {recipe.alternates.map((alt) => (
            <li key={alt.id} className="text-sm">
              <span className="font-medium">{alt.original_value}</span> → {alt.alternate_value}
              {alt.notes && <span className="text-neutral-400"> ({alt.notes})</span>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
