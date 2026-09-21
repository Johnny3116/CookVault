"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api";
import { addDays, fmtDate, startOfWeek, weekDays } from "@/lib/dates";
import type { MealPlanEntry, RecipeSummary } from "@/types";

export default function CalendarPage() {
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [entries, setEntries] = useState<MealPlanEntry[]>([]);
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [selectedRecipeId, setSelectedRecipeId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const days = weekDays(weekStart);
  const thisWeek = startOfWeek(new Date());
  const isCurrentWeek = fmtDate(weekStart) === fmtDate(thisWeek);

  const load = useCallback(async () => {
    const weekEnd = addDays(weekStart, 6);
    const [entriesData, recipesData] = await Promise.all([
      apiFetch<MealPlanEntry[]>(`/meal-plan?start=${fmtDate(weekStart)}&end=${fmtDate(weekEnd)}`),
      apiFetch<RecipeSummary[]>("/recipes"),
    ]);
    setEntries(entriesData);
    setRecipes(recipesData);
  }, [weekStart]);

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, [load]);

  async function run(work: () => Promise<unknown>) {
    setError(null);
    try {
      await work();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  const recipeTitle = (id: string) => recipes.find((r) => r.id === id)?.title ?? "Unknown recipe";

  const weekLabel = `${weekStart.toLocaleDateString(undefined, { month: "short", day: "numeric" })} – ${addDays(
    weekStart,
    6,
  ).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Meal Plan</h1>
        <button
          disabled
          title="Auto-fill isn't built yet — Phase 2 feature"
          className="cursor-not-allowed rounded border border-neutral-300 px-3 py-1 text-sm text-neutral-400"
        >
          Auto-fill week
        </button>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => setWeekStart((current) => addDays(current, -7))}
          aria-label="Previous week"
          className="rounded border border-neutral-300 px-3 py-1 text-sm"
        >
          ←
        </button>
        <span className="min-w-56 text-center text-sm font-medium">{weekLabel}</span>
        <button
          onClick={() => setWeekStart((current) => addDays(current, 7))}
          aria-label="Next week"
          className="rounded border border-neutral-300 px-3 py-1 text-sm"
        >
          →
        </button>
        {!isCurrentWeek && (
          <button
            onClick={() => setWeekStart(startOfWeek(new Date()))}
            className="rounded border border-neutral-300 px-3 py-1 text-sm"
          >
            This week
          </button>
        )}
      </div>

      <select
        value={selectedRecipeId}
        onChange={(e) => setSelectedRecipeId(e.target.value)}
        aria-label="Recipe to assign"
        className="rounded border border-neutral-300 px-3 py-2 text-sm"
      >
        <option value="">Select a recipe to assign…</option>
        {recipes.map((r) => (
          <option key={r.id} value={r.id}>
            {r.title}
          </option>
        ))}
      </select>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-7">
        {days.map((day) => {
          const dayEntries = entries.filter((e) => e.date === fmtDate(day));
          const isToday = fmtDate(day) === fmtDate(new Date());
          return (
            <div
              key={fmtDate(day)}
              className={`rounded border p-2 ${isToday ? "border-neutral-800" : "border-neutral-200"}`}
            >
              <p className="mb-2 text-xs font-semibold text-neutral-500">
                {day.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
              </p>
              <ul className="space-y-1">
                {dayEntries.map((entry) => (
                  <li key={entry.id} className="flex items-start justify-between gap-1 text-xs">
                    <Link href={`/recipes/${entry.recipe_id}`} className="hover:underline">
                      {recipeTitle(entry.recipe_id)}
                    </Link>
                    <button
                      onClick={() => run(() => apiFetch(`/meal-plan/${entry.id}`, { method: "DELETE" }))}
                      aria-label={`Remove ${recipeTitle(entry.recipe_id)}`}
                      className="text-neutral-400 hover:text-red-600"
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
              <button
                onClick={() =>
                  run(() =>
                    apiFetch("/meal-plan", {
                      method: "POST",
                      body: JSON.stringify({
                        date: fmtDate(day),
                        recipe_id: selectedRecipeId,
                        mode: "manual",
                      }),
                    }),
                  )
                }
                disabled={!selectedRecipeId}
                className="mt-2 text-xs text-neutral-500 underline disabled:opacity-40"
              >
                + assign
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
