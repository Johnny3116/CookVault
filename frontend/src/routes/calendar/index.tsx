import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { ChevronLeft, ChevronRight, Plus, Sparkles, X } from "lucide-react";
import { useState } from "react";

import { ErrorText, PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { apiFetch, json } from "@/lib/api";
import { addDays, fmtDate, startOfWeek, weekDays } from "@/lib/dates";
import { describeApiError } from "@/lib/errors";
import type { MealPlanDraftDetail, MealPlanEntry, MealType, RecipeSummary } from "@/types";

const MEAL_TYPES: MealType[] = ["breakfast", "lunch", "dinner", "snack"];

export const Route = createFileRoute("/calendar/")({
  head: () => ({ meta: [{ title: "Meal plan — CookVault" }] }),
  component: CalendarPage,
});

function CalendarPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [selectedRecipeId, setSelectedRecipeId] = useState("");
  const [plannedServings, setPlannedServings] = useState("");
  const [mealType, setMealType] = useState<MealType | "">("dinner");
  const [error, setError] = useState<string | null>(null);

  const weekKey = fmtDate(weekStart);
  const entries = useQuery({
    queryKey: ["meal-plan", weekKey],
    queryFn: () => apiFetch<MealPlanEntry[]>(`/meal-plan?start=${weekKey}&end=${fmtDate(addDays(weekStart, 6))}`),
  });
  const recipes = useQuery({ queryKey: ["recipes"], queryFn: () => apiFetch<RecipeSummary[]>("/recipes") });
  const waiting = useQuery({
    queryKey: ["meal-plan-drafts", "ready"],
    queryFn: () => apiFetch<MealPlanDraftDetail[]>("/meal-plan/drafts?status_filter=ready"),
  });

  const refresh = () => {
    setError(null);
    queryClient.invalidateQueries({ queryKey: ["meal-plan"] });
  };
  const assign = useMutation({
    mutationFn: (date: string) =>
      apiFetch(
        "/meal-plan",
        json("POST", {
          date,
          recipe_id: selectedRecipeId,
          mode: "manual",
          meal_type: mealType || null,
          servings: plannedServings ? Number(plannedServings) : null,
        }),
      ),
    onSuccess: refresh,
    onError: (err) => setError(describeApiError(err)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiFetch(`/meal-plan/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
    onError: (err) => setError(describeApiError(err)),
  });
  /** Propose a week and go and look at it. Deliberately two steps: filling
   *  the calendar directly would make the suggestion an action. */
  const propose = useMutation({
    mutationFn: () =>
      apiFetch<MealPlanDraftDetail>("/meal-plan/auto-fill", json("POST", { start: weekKey, days: 7, meal_type: mealType || "dinner" })),
    onSuccess: (draft) => {
      queryClient.invalidateQueries({ queryKey: ["meal-plan-drafts"] });
      navigate({ to: "/calendar/proposals", hash: draft.id });
    },
    onError: (err) => setError(describeApiError(err)),
  });

  const all = recipes.data ?? [];
  const list = entries.data ?? [];
  const titleOf = (id: string) => all.find((r) => r.id === id)?.title ?? "Unknown recipe";
  const selectedRecipe = all.find((r) => r.id === selectedRecipeId);
  const days = weekDays(weekStart);
  const isCurrentWeek = weekKey === fmtDate(startOfWeek(new Date()));
  const today = fmtDate(new Date());
  const waitingCount = waiting.data?.length ?? 0;
  const weekLabel = `${weekStart.toLocaleDateString(undefined, { month: "short", day: "numeric" })} – ${addDays(weekStart, 6).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;

  return (
    <div>
      <PageHeader
        eyebrow="Meal plan"
        title="This week's plan"
        intro="Pick a recipe, then add it to a night. Or let CookVault propose a week from your cooking history — nothing is planned until you approve it."
        actions={
          <>
            {waitingCount > 0 && (
              <Button asChild variant="secondary" className="glass-button">
                <Link to="/calendar/proposals">
                  {waitingCount} proposed {waitingCount === 1 ? "week" : "weeks"} waiting
                </Link>
              </Button>
            )}
            <Button onClick={() => propose.mutate()} disabled={propose.isPending || all.length === 0} title="Suggests a week from your cooking history. Nothing is planned until you approve it.">
              <Sparkles /> {propose.isPending ? "Proposing…" : "Propose a week"}
            </Button>
          </>
        }
      />

      <div className="glass-panel mb-5 flex flex-wrap items-center gap-2 p-3">
        <Button size="icon-sm" variant="ghost" aria-label="Previous week" onClick={() => setWeekStart((c) => addDays(c, -7))}>
          <ChevronLeft />
        </Button>
        <span className="min-w-52 text-center text-sm font-semibold">{weekLabel}</span>
        <Button size="icon-sm" variant="ghost" aria-label="Next week" onClick={() => setWeekStart((c) => addDays(c, 7))}>
          <ChevronRight />
        </Button>
        {!isCurrentWeek && (
          <button className="chip" onClick={() => setWeekStart(startOfWeek(new Date()))}>
            This week
          </button>
        )}
        <span className="flex-1" />
        <select
          value={selectedRecipeId}
          onChange={(e) => {
            setSelectedRecipeId(e.target.value);
            setPlannedServings("");
          }}
          aria-label="Recipe to assign"
          className="field field-sm w-auto max-w-64"
        >
          <option value="">Select a recipe to add…</option>
          {all.map((r) => (
            <option key={r.id} value={r.id}>
              {r.title}
            </option>
          ))}
        </select>
        <select value={mealType} onChange={(e) => setMealType(e.target.value as MealType | "")} aria-label="Meal" className="field field-sm w-auto">
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
          className="field field-sm w-36"
        />
      </div>

      <ErrorText>{error}</ErrorText>

      <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        {days.map((day) => {
          const key = fmtDate(day);
          const dayEntries = list.filter((e) => e.date === key);
          return (
            <div key={key} className={`day-card glass-panel ${key === today ? "is-today" : ""}`}>
              <p className="text-xs font-semibold uppercase text-muted-foreground">
                {day.toLocaleDateString(undefined, { weekday: "short" })}{" "}
                <span className="font-normal normal-case">{day.toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
              </p>
              {dayEntries.map((entry) => (
                <div key={entry.id} className="meal">
                  <span className="min-w-0">
                    <Link to="/recipes/$id" params={{ id: entry.recipe_id }} search={entry.servings ? { servings: entry.servings } : {}} className="font-semibold hover:underline">
                      {titleOf(entry.recipe_id)}
                    </Link>
                    {(entry.servings || entry.meal_type) && (
                      <small>{[entry.meal_type, entry.servings ? `serves ${entry.servings}` : null].filter(Boolean).join(" · ")}</small>
                    )}
                  </span>
                  <button onClick={() => remove.mutate(entry.id)} aria-label={`Remove ${titleOf(entry.recipe_id)}`} className="text-muted-foreground/60 hover:text-destructive">
                    <X className="size-3.5" />
                  </button>
                </div>
              ))}
              <button
                onClick={() => assign.mutate(key)}
                disabled={!selectedRecipeId || assign.isPending}
                className="mt-auto inline-flex items-center gap-1 text-xs font-semibold text-primary disabled:opacity-40"
              >
                <Plus className="size-3.5" /> add
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
