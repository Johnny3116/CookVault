"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { MealPlanDraftDetail, PlannedMeal, RecipeSummary } from "@/types";

/** Proposed weeks, waiting to be said yes to.
 *
 * The review surface for auto-fill and for anything the agent proposes. The
 * thing it has to make easy is disagreeing: a plan you can only accept whole
 * or reject whole is one you reject, so every meal here can be swapped or
 * dropped before approving.
 */
export default function ProposalsPage() {
  const [drafts, setDrafts] = useState<MealPlanDraftDetail[]>([]);
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [list, recipeList] = await Promise.all([
      apiFetch<MealPlanDraftDetail[]>("/meal-plan/drafts"),
      apiFetch<RecipeSummary[]>("/recipes"),
    ]);
    // The list endpoint returns summaries; the meals live on the detail.
    const detailed = await Promise.all(
      list.map((d) => apiFetch<MealPlanDraftDetail>(`/meal-plan/drafts/${d.id}`)),
    );
    setDrafts(detailed);
    setRecipes(recipeList);
  }, []);

  useEffect(() => {
    load().catch((err) => setError(describeApiError(err)));
  }, [load]);

  async function run(work: () => Promise<unknown>) {
    setError(null);
    setBusy(true);
    try {
      await work();
      await load();
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setBusy(false);
    }
  }

  const titleOf = (id: string) => recipes.find((r) => r.id === id)?.title ?? "(recipe deleted)";

  async function swap(draft: MealPlanDraftDetail, index: number, recipeId: string) {
    const meals: PlannedMeal[] = draft.meals.map((meal, i) =>
      // Swapping a meal makes the old reason a lie, so it goes with it.
      i === index ? { ...meal, recipe_id: recipeId, reason: null } : meal,
    );
    await run(() =>
      apiFetch(`/meal-plan/drafts/${draft.id}`, {
        method: "PATCH",
        body: JSON.stringify({ meals }),
      }),
    );
  }

  async function drop(draft: MealPlanDraftDetail, index: number) {
    const meals = draft.meals.filter((_, i) => i !== index);
    await run(() =>
      apiFetch(`/meal-plan/drafts/${draft.id}`, {
        method: "PATCH",
        body: JSON.stringify({ meals }),
      }),
    );
  }

  const open = drafts.filter((d) => d.status === "draft" || d.status === "ready");
  const settled = drafts.filter((d) => d.status === "promoted" || d.status === "discarded");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Proposed weeks</h1>
          <p className="mt-1 max-w-2xl text-sm text-neutral-500">
            Nothing here is on the calendar. Approving a plan is what creates the entries — and
            you can swap or drop any meal first.
          </p>
        </div>
        <Link href="/calendar" className="rounded border border-neutral-300 px-3 py-2 text-sm">
          Back to calendar
        </Link>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {open.length === 0 && (
        <p className="text-neutral-500">
          No proposals waiting. Use <span className="font-medium">Propose a week</span> on the
          calendar.
        </p>
      )}

      {open.map((draft) => (
        <section key={draft.id} className="rounded border border-neutral-200 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-medium">{draft.title?.trim() || "Untitled plan"}</h2>
              <p className="text-xs text-neutral-400">
                {draft.created_by === "agent"
                  ? `proposed by ${draft.agent_model ?? "an agent"}`
                  : "proposed by CookVault from your cooking history"}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => run(() => apiFetch(`/meal-plan/drafts/${draft.id}/discard`, { method: "POST" }))}
                disabled={busy}
                className="rounded border border-neutral-300 px-3 py-1 text-sm disabled:opacity-40"
              >
                Discard
              </button>
              <button
                onClick={() => run(() => apiFetch(`/meal-plan/drafts/${draft.id}/approve`, { method: "POST" }))}
                disabled={busy || draft.meals.length === 0}
                className="rounded bg-neutral-800 px-3 py-1 text-sm text-white disabled:opacity-40"
              >
                Approve {draft.meals.length} {draft.meals.length === 1 ? "meal" : "meals"}
              </button>
            </div>
          </div>

          {draft.note && <p className="mt-2 text-sm text-neutral-600">{draft.note}</p>}

          <ul className="mt-3 divide-y divide-neutral-100">
            {draft.meals.map((meal, index) => (
              <li key={`${meal.date}-${index}`} className="flex flex-wrap items-center gap-3 py-2">
                <span className="w-28 shrink-0 text-xs font-medium text-neutral-500">
                  {new Date(`${meal.date}T00:00:00`).toLocaleDateString(undefined, {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                  })}
                </span>
                <select
                  value={meal.recipe_id}
                  onChange={(e) => swap(draft, index, e.target.value)}
                  aria-label={`Recipe for ${meal.date}`}
                  className="min-w-0 flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
                >
                  {!recipes.some((r) => r.id === meal.recipe_id) && (
                    <option value={meal.recipe_id}>{titleOf(meal.recipe_id)}</option>
                  )}
                  {recipes.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.title}
                    </option>
                  ))}
                </select>
                {/* Why this recipe on this day. The whole reason the plan is
                    arguable rather than something to accept on faith. Fixed
                    width so the selects line up instead of stepping in and out
                    with the length of the reason. */}
                <span
                  title={meal.reason ?? "swapped by you"}
                  className="w-48 shrink-0 truncate text-xs text-neutral-400"
                >
                  {meal.reason ?? "swapped by you"}
                </span>
                <button
                  onClick={() => drop(draft, index)}
                  aria-label={`Drop ${meal.date}`}
                  className="text-neutral-400 hover:text-red-600"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {settled.length > 0 && (
        <details className="rounded border border-neutral-200 p-4">
          <summary className="cursor-pointer text-sm text-neutral-500">
            {settled.length} settled {settled.length === 1 ? "plan" : "plans"}
          </summary>
          <ul className="mt-3 space-y-1 text-sm">
            {settled.map((draft) => (
              <li key={draft.id} className="flex items-center justify-between gap-3">
                <span>{draft.title?.trim() || "Untitled plan"}</span>
                <span className="text-xs text-neutral-400">{draft.status}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
