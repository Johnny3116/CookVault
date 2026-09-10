"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { RecipeCard } from "@/components/RecipeCard";
import { apiFetch } from "@/lib/api";
import type { RecipeSummary } from "@/types";

function LibraryContent() {
  const searchParams = useSearchParams();
  const favoriteOnly = searchParams.get("favorite") === "true";
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);

  useEffect(() => {
    const query = favoriteOnly ? "?favorite=true" : "";
    apiFetch<RecipeSummary[]>(`/recipes${query}`).then(setRecipes);
  }, [favoriteOnly]);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Recipe Library</h1>
        <a href={favoriteOnly ? "/library" : "/library?favorite=true"} className="text-sm underline">
          {favoriteOnly ? "Show all" : "Favorites only"}
        </a>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
        {recipes.map((recipe) => (
          <RecipeCard key={recipe.id} recipe={recipe} />
        ))}
        {recipes.length === 0 && <p className="text-neutral-500">No recipes found.</p>}
      </div>
    </div>
  );
}

export default function LibraryPage() {
  return (
    <Suspense fallback={<p className="text-neutral-500">Loading…</p>}>
      <LibraryContent />
    </Suspense>
  );
}
