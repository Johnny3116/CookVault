"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import { addDays, fmtDate, startOfWeek, weekDays } from "@/lib/dates";
import type { MealPlanDraftDetail, MealPlanEntry, MealType, RecipeSummary } from "@/types";

const MEAL_TYPES: MealType[] = ["breakfast", "lunch", "dinner", "snack"];

export default function CalendarPage() {
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [entries, setEntries] = useState<MealPlanEntry[]>([]);
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [selectedRecipeId, setSelectedRecipeId] = useState("");
  // Servings planned for the day. Blank means "as the recipe is written".
  const [plannedServings, setPlannedServings] = useState("");
  const [mealType, setMealType] = useState<MealType | "">("dinner");
  const [error, setError] = useState<string | null>(null);
  const [proposing, setProposing] = useState(false);
  const [waiting, setWaiting] = useState(0);
  const router = useRouter();

  const days = weekDays(weekStart);
  const thisWeek = startOfWeek(new Date());
  const isCurrentWeek = fmtDate(weekStart) === fmtDate(thisWeek);

  const load = useCallback(async () => {
    const weekEnd = addDays(weekStart, 6);
    const [entriesData, recipesData, proposals] = await Promise.all([
      apiFetch<MealPlanEntry[]>(`/meal-plan?start=${fmtDate(weekStart)}&end=${fmtDate(weekEnd)}`),
      apiFetch<RecipeSummary[]>("/recipes"),
      apiFetch<MealPlanDraftDetail[]>("/meal-plan/drafts?status_filter=ready"),
    ]);
    setEntries(entriesData);
    setRecipes(recipesData);
    setWaiting(proposals.length);
  }, [weekStart]);

  useEffect(() => {
    load().catch((err) => setError(describeApiError(err)));
  }, [load]);

  async function run(work: () => Promise<unknown>) {
    setError(null);
    try {
      await work();
      await load();
    } catch (err) {
      setError(describeApiError(err));
    }
  }

  /** Propose a week and go and look at it.
   *
   * Deliberately two steps. Filling the calendar directly would make the
   * suggestion an action instead of a suggestion, and the whole reason this is
   * arithmetic over the cook log is that it can be argued with.
   */
  async function proposeWeek() {
    setError(null);
    setProposing(true);
    try {
      const draft = await apiFetch<MealPlanDraftDetail>("/meal-plan/auto-fill", {
        method: "POST",
        body: JSON.stringify({
          start: fmtDate(weekStart),
          days: 7,
          meal_type: mealType || "dinner",
        }),
      });
      router.push(`/calendar/proposals#${draft.id}`);
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setProposing(false);
    }
  }

  const recipeTitle = (id: string) => recipes.find((r) => r.id === id)?.title ?? "Unknown recipe";
  const selectedRecipe = recipes.find((r) => r.id === selectedRecipeId);

  const weekLabel = `${weekStart.toLocaleDateString(undefined, { month: "short", day: "numeric" })} – ${addDays(
    weekStart,
    6,
  ).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Meal Plan</h1>
        <div className="flex items-center gap-2">
          {waiting > 0 && (
            <Link href="/calendar/proposals" className="text-sm text-neutral-500 underline">
              {waiting} proposed {waiting === 1 ? "week" : "weeks"} waiting
            </Link>
          )}
          <button
            onClick={proposeWeek}
            disabled={proposing || recipes.length === 0}
            title="Suggests a week from your cooking history. Nothing is planned until you approve it."
            className="rounded border border-neutral-300 px-3 py-1 text-sm disabled:opacity-40"
          >
            {proposing ? "Proposing…" : "Propose a week"}
          </button>
        </div>
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

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={selectedRecipeId}
          onChange={(e) => {
            setSelectedRecipeId(e.target.value);
            setPlannedServings("");
          }}
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
        <select
          value={mealType}
          onChange={(e) => setMealType(e.target.value as MealType | "")}
          aria-label="Meal"
          className="rounded border border-neutral-300 px-3 py-2 text-sm"
        >
          <option value="">Any meal</option>
          {MEAL_TYPES.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <input
          type="number"
          min={1}
          placeholder={selectedRecipe?.servings ? `${selectedRecipe.servings} (as written)` : "servings"}
          value={plannedServings}
          onChange={(e) => setPlannedServings(e.target.value)}
          aria-label="Servings to plan"
          className="w-40 rounded border border-neutral-300 px-3 py-2 text-sm"
        />
        <span className="text-xs text-neutral-500">
          Servings carry through to the shopping list.
        </span>
      </div>

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
                    <span className="min-w-0">
                      <Link
                        href={`/recipes/${entry.recipe_id}${entry.servings ? `?servings=${entry.servings}` : ""}`}
                        className="hover:underline"
                      >
                        {recipeTitle(entry.recipe_id)}
                      </Link>
                      {(entry.servings || entry.meal_type) && (
                        <span className="block text-[10px] text-neutral-400">
                          {[entry.meal_type, entry.servings ? `serves ${entry.servings}` : null]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      )}
                    </span>
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
                        meal_type: mealType || null,
                        servings: plannedServings ? Number(plannedServings) : null,
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
