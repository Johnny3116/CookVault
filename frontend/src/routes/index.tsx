import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import { Check, Plus } from "lucide-react";

import { EmptyState, SectionHeading } from "@/components/PageHeader";
import { RecipeCard } from "@/components/RecipeCard";
import { Button } from "@/components/ui/button";
import { apiFetch, json } from "@/lib/api";
import { addDays, fmtDate, startOfWeek, weekDays } from "@/lib/dates";
import { ingredientLabel } from "@/lib/format";
import { formatMinutes, totalMinutes } from "@/lib/recipes";
import type { MealPlanEntry, RecipeSummary, ShoppingListItem } from "@/types";

export const Route = createFileRoute("/")({
  head: () => ({ meta: [{ title: "CookVault — What sounds good tonight?" }] }),
  component: Dashboard,
});

function Dashboard() {
  const queryClient = useQueryClient();
  const weekStart = startOfWeek(new Date());
  const weekEnd = addDays(weekStart, 6);

  const recipes = useQuery({ queryKey: ["recipes"], queryFn: () => apiFetch<RecipeSummary[]>("/recipes") });
  const plan = useQuery({
    queryKey: ["meal-plan", fmtDate(weekStart)],
    queryFn: () => apiFetch<MealPlanEntry[]>(`/meal-plan?start=${fmtDate(weekStart)}&end=${fmtDate(weekEnd)}`),
  });
  const shopping = useQuery({ queryKey: ["shopping-list"], queryFn: () => apiFetch<ShoppingListItem[]>("/shopping-list") });

  const toggleFavorite = useMutation({
    mutationFn: (recipe: RecipeSummary) =>
      apiFetch(`/recipes/${recipe.id}`, json("PATCH", { is_favorite: !recipe.is_favorite })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["recipes"] }),
  });
  const toggleChecked = useMutation({
    mutationFn: (item: ShoppingListItem) =>
      apiFetch(`/shopping-list/${item.id}`, json("PATCH", { is_checked: !item.is_checked })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["shopping-list"] }),
  });

  const all = recipes.data ?? [];
  const favorites = all.filter((r) => r.is_favorite).length;
  const titleOf = (id: string) => all.find((r) => r.id === id);
  const days = weekDays(weekStart);
  const entries = plan.data ?? [];
  const items = shopping.data ?? [];
  const unchecked = items.filter((i) => !i.is_checked);
  const preview = [...unchecked, ...items.filter((i) => i.is_checked)].slice(0, 6);
  const today = fmtDate(new Date());

  return (
    <div>
      <section className="flex flex-col gap-6 lg:flex-row lg:items-end">
        <div className="flex-1">
          <p className="eyebrow">Your kitchen</p>
          <h1 className="mt-2 font-display text-4xl font-semibold leading-tight sm:text-5xl">What sounds good tonight?</h1>
          <p className="mt-3 max-w-xl text-base leading-relaxed text-muted-foreground">
            Every well-loved recipe in one place, then the week's picks turned into a plan and a tidy shopping list.
          </p>
        </div>
        <div className="flex gap-3">
          <div className="glass-panel stat-tile">
            <strong>{all.length}</strong>
            <small>Saved recipes</small>
          </div>
          <div className="glass-panel stat-tile">
            <strong>{favorites}</strong>
            <small>Favorites</small>
          </div>
          <div className="glass-panel stat-tile">
            <strong>{entries.length}</strong>
            <small>Meals this week</small>
          </div>
        </div>
      </section>

      <section className="mt-8 grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-7">
          <SectionHeading
            title="This week's plan"
            detail={`${new Set(entries.map((e) => e.date)).size} of 7 nights set`}
            action={
              <Link to="/calendar" className="text-primary underline">
                Open calendar
              </Link>
            }
          />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 xl:grid-cols-4">
            {days.map((day) => {
              const key = fmtDate(day);
              const dayEntries = entries.filter((e) => e.date === key);
              const label = day.toLocaleDateString(undefined, { weekday: "short" });
              if (dayEntries.length === 0) {
                return (
                  <Link key={key} to="/calendar" className="plan-card plan-empty flex flex-col">
                    <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
                    <h3 className="mt-2 font-display text-lg font-medium leading-tight text-muted-foreground">Add a recipe</h3>
                    <p className="mt-auto text-xs text-muted-foreground">Plan this night</p>
                  </Link>
                );
              }
              const first = dayEntries[0]!;
              const recipe = titleOf(first.recipe_id);
              const minutes = recipe ? formatMinutes(totalMinutes(recipe)) : null;
              return (
                <Link
                  key={key}
                  to="/recipes/$id"
                  params={{ id: first.recipe_id }}
                  search={first.servings ? { servings: first.servings } : {}}
                  className="plan-card glass-panel flex flex-col"
                >
                  <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
                  <h3 className="mt-2 min-h-11 font-display text-lg font-medium leading-tight">
                    {recipe?.title ?? "Unknown recipe"}
                    {dayEntries.length > 1 && <span className="text-muted-foreground"> +{dayEntries.length - 1}</span>}
                  </h3>
                  <div className="mt-auto flex items-center justify-between gap-2 text-xs text-muted-foreground">
                    <span>{minutes ?? first.meal_type ?? ""}</span>
                    {key === today ? <span className="status-honey">Tonight</span> : <span className="status-mint">Set</span>}
                  </div>
                </Link>
              );
            })}
          </div>
        </div>

        <div className="col-span-12 lg:col-span-5">
          <SectionHeading title="Shopping list" detail={`${unchecked.length} left`} />
          <div className="glass-panel p-5">
            {preview.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nothing on the list yet.</p>
            ) : (
              <ul className="space-y-2">
                {preview.map((item) => (
                  <li key={item.id} className="flex items-center gap-3 rounded-xl px-2 py-1.5">
                    <button
                      className={`check-control ${item.is_checked ? "is-checked" : ""}`}
                      aria-label={`${item.is_checked ? "Uncheck" : "Check"} ${item.name}`}
                      onClick={() => toggleChecked.mutate(item)}
                    >
                      {item.is_checked && <Check />}
                    </button>
                    <span className={`min-w-0 flex-1 text-sm font-medium ${item.is_checked ? "text-muted-foreground line-through" : ""}`}>
                      {ingredientLabel(item)}
                    </span>
                    <span className="text-xs capitalize text-muted-foreground">{item.aisle.replace("_", " & ")}</span>
                  </li>
                ))}
              </ul>
            )}
            <Button asChild className="mt-5 w-full rounded-xl">
              <Link to="/shopping-list">{items.length > 6 ? `See all ${items.length} items` : "Open the shopping list"}</Link>
            </Button>
          </div>
        </div>
      </section>

      <section className="mt-10">
        <SectionHeading
          title="Recent recipes"
          detail={`${all.length} saved · ${favorites} favorites`}
          action={
            <Link to="/library" className="text-primary underline">
              Browse the library
            </Link>
          }
        />
        {recipes.isLoading ? (
          <div className="glass-panel p-10 text-center text-muted-foreground">Opening your recipe vault…</div>
        ) : recipes.error ? (
          <div className="glass-panel p-10 text-center text-destructive">Your recipes could not be loaded.</div>
        ) : all.length === 0 ? (
          <EmptyState title="No recipes yet">
            Add your first one, paste one in, or ask Sage to draft one from a conversation.
          </EmptyState>
        ) : (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {all.slice(0, 8).map((recipe) => (
              <RecipeCard key={recipe.id} recipe={recipe} onFavorite={(r) => toggleFavorite.mutate(r)} />
            ))}
            {all.length < 4 && (
              <Link to="/recipes/new" className="plan-empty flex min-h-48 flex-col items-center justify-center rounded-[1.15rem] text-muted-foreground">
                <Plus className="size-6" />
                <span className="mt-2 text-sm font-semibold">Add a recipe</span>
              </Link>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
