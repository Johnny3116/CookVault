import Link from "next/link";

import type { RecipeSummary } from "@/types";

export function RecipeCard({ recipe }: { recipe: RecipeSummary }) {
  return (
    <Link
      href={`/recipes/${recipe.id}`}
      className="block rounded-lg border border-neutral-200 p-4 hover:border-neutral-400"
    >
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">{recipe.title}</h3>
        {recipe.is_favorite && <span title="Favorite">⭐</span>}
      </div>
      <p className="mt-1 text-sm text-neutral-500">
        {recipe.prep_time ? `${recipe.prep_time}m prep` : ""}
        {recipe.cook_time ? ` · ${recipe.cook_time}m cook` : ""}
        {recipe.servings ? ` · serves ${recipe.servings}` : ""}
      </p>
      {recipe.tags.length > 0 && <p className="mt-2 text-xs text-neutral-400">{recipe.tags.join(" · ")}</p>}
    </Link>
  );
}
