"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { RecipeCard } from "@/components/RecipeCard";
import { apiFetch } from "@/lib/api";
import { addDays, fmtDate, startOfWeek } from "@/lib/dates";
import type { MealPlanEntry, RecipeSummary } from "@/types";

export default function DashboardPage() {
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [mealPlan, setMealPlan] = useState<MealPlanEntry[]>([]);

  useEffect(() => {
    const weekStart = startOfWeek(new Date());
    const weekEnd = addDays(weekStart, 6);

    apiFetch<RecipeSummary[]>("/recipes").then(setRecipes).catch(() => {});
    apiFetch<MealPlanEntry[]>(`/meal-plan?start=${fmtDate(weekStart)}&end=${fmtDate(weekEnd)}`)
      .then(setMealPlan)
      .catch(() => {});
  }, []);

  const recent = recipes.slice(0, 6);
  const titleFor = (recipeId: string) => recipes.find((r) => r.id === recipeId)?.title;

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
        {mealPlan.length === 0 ? (
          <p className="text-sm text-neutral-500">
            Nothing planned this week.{" "}
            <Link href="/calendar" className="underline">
              Plan some meals
            </Link>
            .
          </p>
        ) : (
          <ul className="space-y-1 text-sm">
            {mealPlan.map((entry) => (
              <li key={entry.id}>
                <span className="text-neutral-500">
                  {new Date(`${entry.date}T00:00:00`).toLocaleDateString(undefined, {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                  })}
                </span>{" "}
                —{" "}
                <Link href={`/recipes/${entry.recipe_id}`} className="underline">
                  {titleFor(entry.recipe_id) ?? "Unknown recipe"}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
