"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import type { MealPlanEntry, RecipeSummary } from "@/types";

function startOfWeek(date: Date) {
  const d = new Date(date);
  d.setDate(d.getDate() - d.getDay());
  d.setHours(0, 0, 0, 0);
  return d;
}

function fmt(d: Date) {
  return d.toISOString().slice(0, 10);
}

export default function CalendarPage() {
  const [weekStart] = useState(() => startOfWeek(new Date()));
  const [entries, setEntries] = useState<MealPlanEntry[]>([]);
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [selectedRecipeId, setSelectedRecipeId] = useState("");

  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart);
    d.setDate(weekStart.getDate() + i);
    return d;
  });

  async function load() {
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekStart.getDate() + 6);
    const [entriesData, recipesData] = await Promise.all([
      apiFetch<MealPlanEntry[]>(`/meal-plan?start=${fmt(weekStart)}&end=${fmt(weekEnd)}`),
      apiFetch<RecipeSummary[]>("/recipes"),
    ]);
    setEntries(entriesData);
    setRecipes(recipesData);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function assign(date: Date) {
    if (!selectedRecipeId) return;
    await apiFetch("/meal-plan", {
      method: "POST",
      body: JSON.stringify({ date: fmt(date), recipe_id: selectedRecipeId, mode: "manual" }),
    });
    load();
  }

  async function removeEntry(id: string) {
    await apiFetch(`/meal-plan/${id}`, { method: "DELETE" });
    load();
  }

  const recipeTitle = (id: string) => recipes.find((r) => r.id === id)?.title ?? "Unknown recipe";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Meal Plan</h1>
        <button
          disabled
          title="Auto-fill isn't built yet — Phase 2 feature"
          className="cursor-not-allowed rounded border border-neutral-300 px-3 py-1 text-sm text-neutral-400"
        >
          Auto-fill week
        </button>
      </div>

      <select
        value={selectedRecipeId}
        onChange={(e) => setSelectedRecipeId(e.target.value)}
        className="rounded border border-neutral-300 px-3 py-2 text-sm"
      >
        <option value="">Select a recipe to assign…</option>
        {recipes.map((r) => (
          <option key={r.id} value={r.id}>
            {r.title}
          </option>
        ))}
      </select>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-7">
        {days.map((day) => {
          const dayEntries = entries.filter((e) => e.date === fmt(day));
          return (
            <div key={fmt(day)} className="rounded border border-neutral-200 p-2">
              <p className="mb-2 text-xs font-semibold text-neutral-500">
                {day.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
              </p>
              <ul className="space-y-1">
                {dayEntries.map((entry) => (
                  <li key={entry.id} className="flex items-center justify-between text-xs">
                    <span>{recipeTitle(entry.recipe_id)}</span>
                    <button onClick={() => removeEntry(entry.id)} className="text-neutral-400">
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
              <button onClick={() => assign(day)} className="mt-2 text-xs text-neutral-500 underline">
                + assign
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
