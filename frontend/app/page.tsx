"use client";

import { useEffect, useState } from "react";

import { RecipeCard } from "@/components/RecipeCard";
import { apiFetch } from "@/lib/api";
import type { MealPlanEntry, RecipeSummary } from "@/types";

function fmt(d: Date) {
  return d.toISOString().slice(0, 10);
}

export default function DashboardPage() {
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [mealPlan, setMealPlan] = useState<MealPlanEntry[]>([]);

  useEffect(() => {
    apiFetch<RecipeSummary[]>("/recipes").then(setRecipes);

    const today = new Date();
    const weekStart = new Date(today);
    weekStart.setDate(today.getDate() - today.getDay());
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekStart.getDate() + 6);

    apiFetch<MealPlanEntry[]>(`/meal-plan?start=${fmt(weekStart)}&end=${fmt(weekEnd)}`).then(setMealPlan);
  }, []);

  const recent = recipes.slice(0, 6);

  return (
    <div className="space-y-10">
      <section>
        <h2 className="mb-4 text-lg font-semibold">Recent Recipes</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
          {recent.map((recipe) => (
            <RecipeCard key={recipe.id} recipe={recipe} />
          ))}
          {recent.length === 0 && <p className="text-neutral-500">No recipes yet — add your first one.</p>}
        </div>
      </section>
      <section>
        <h2 className="mb-4 text-lg font-semibold">This Week&apos;s Meals</h2>
        <p className="text-sm text-neutral-500">{mealPlan.length} meal(s) planned this week.</p>
      </section>
    </div>
  );
}
