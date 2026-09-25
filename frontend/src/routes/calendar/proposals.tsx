import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import { X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState, ErrorText, PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { apiFetch, json } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { MealPlanDraftDetail, MealPlanDraftSummary, PlannedMeal, RecipeSummary } from "@/types";

export const Route = createFileRoute("/calendar/proposals")({
  head: () => ({ meta: [{ title: "Proposed weeks — CookVault" }] }),
  component: ProposalsPage,
});

/** Proposed weeks, waiting to be said yes to.
 *
 * The review surface for auto-fill and for anything ChefNexus proposes. The thing
 * it has to make easy is disagreeing: a plan you can only accept whole or
 * reject whole is one you reject, so every meal can be swapped or dropped.
 */
function ProposalsPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const drafts = useQuery({
    queryKey: ["meal-plan-drafts", "all"],
    queryFn: async () => {
      // The list endpoint returns summaries; the meals live on the detail.
      const list = await apiFetch<MealPlanDraftSummary[]>("/meal-plan/drafts");
      return Promise.all(list.map((d) => apiFetch<MealPlanDraftDetail>(`/meal-plan/drafts/${d.id}`)));
    },
  });
  const recipes = useQuery({ queryKey: ["recipes"], queryFn: () => apiFetch<RecipeSummary[]>("/recipes") });

  const mutation = useMutation({
    mutationFn: (work: () => Promise<unknown>) => work(),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["meal-plan-drafts"] });
      queryClient.invalidateQueries({ queryKey: ["meal-plan"] });
    },
    onError: (err) => setError(describeApiError(err)),
  });
  const run = (work: () => Promise<unknown>) => mutation.mutate(work);
  const busy = mutation.isPending;

  const all = recipes.data ?? [];
  const titleOf = (id: string) => all.find((r) => r.id === id)?.title ?? "(recipe deleted)";

  const patchMeals = (draft: MealPlanDraftDetail, meals: PlannedMeal[]) =>
    run(() => apiFetch(`/meal-plan/drafts/${draft.id}`, json("PATCH", { meals })));

  const open = (drafts.data ?? []).filter((d) => d.status === "draft" || d.status === "ready");
  const settled = (drafts.data ?? []).filter((d) => d.status === "promoted" || d.status === "discarded");

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Proposals"
        title="Proposed weeks"
        intro="Nothing here is on the calendar. Approving a plan is what creates the entries — and you can swap or drop any meal first."
        actions={
          <Button asChild variant="secondary" className="glass-button">
            <Link to="/calendar">Back to calendar</Link>
          </Button>
        }
      />

      <ErrorText>{error}</ErrorText>

      {drafts.data && open.length === 0 && (
        <EmptyState title="No proposals waiting">
          Use <strong>Propose a week</strong> on the calendar, or ask ChefNexus to plan one.
        </EmptyState>
      )}

      {open.map((draft) => (
        <section key={draft.id} id={draft.id} className="glass-panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-display text-xl font-semibold">{draft.title?.trim() || "Untitled plan"}</h2>
              <p className="text-xs text-muted-foreground">
                {draft.created_by === "agent" ? `proposed by ChefNexus${draft.agent_model ? ` (${draft.agent_model})` : ""}` : "proposed by CookVault from your cooking history"}
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" className="glass-button" disabled={busy} onClick={() => run(() => apiFetch(`/meal-plan/drafts/${draft.id}/discard`, { method: "POST" }))}>
                Discard
              </Button>
              <Button
                disabled={busy || draft.meals.length === 0}
                onClick={() =>
                  run(async () => {
                    await apiFetch(`/meal-plan/drafts/${draft.id}/approve`, { method: "POST" });
                    toast.success("Week approved and on the calendar.");
                  })
                }
              >
                Approve {draft.meals.length} {draft.meals.length === 1 ? "meal" : "meals"}
              </Button>
            </div>
          </div>

          {draft.note && <p className="mt-2 text-sm text-muted-foreground">{draft.note}</p>}

          <ul className="list-rows mt-3">
            {draft.meals.map((meal, index) => (
              <li key={`${meal.date}-${index}`} className="flex flex-wrap items-center gap-3">
                <span className="w-28 shrink-0 text-xs font-semibold text-muted-foreground">
                  {new Date(`${meal.date}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
                </span>
                <select
                  value={meal.recipe_id}
                  onChange={(e) =>
                    // Swapping a meal makes the old reason a lie, so it goes with it.
                    patchMeals(
                      draft,
                      draft.meals.map((m, i) => (i === index ? { ...m, recipe_id: e.target.value, reason: null } : m)),
                    )
                  }
                  aria-label={`Recipe for ${meal.date}`}
                  className="field field-sm min-w-0 flex-1"
                >
                  {!all.some((r) => r.id === meal.recipe_id) && <option value={meal.recipe_id}>{titleOf(meal.recipe_id)}</option>}
                  {all.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.title}
                    </option>
                  ))}
                </select>
                {/* Why this recipe on this day: the whole reason the plan is
                    arguable rather than something to accept on faith. */}
                <span title={meal.reason ?? "swapped by you"} className="w-48 shrink-0 truncate text-xs text-muted-foreground">
                  {meal.reason ?? "swapped by you"}
                </span>
                <button
                  onClick={() =>
                    patchMeals(
                      draft,
                      draft.meals.filter((_, i) => i !== index),
                    )
                  }
                  aria-label={`Drop ${meal.date}`}
                  className="text-muted-foreground/50 hover:text-destructive"
                >
                  <X className="size-4" />
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {settled.length > 0 && (
        <details className="glass-panel p-5">
          <summary className="cursor-pointer text-sm font-semibold text-muted-foreground">
            {settled.length} settled {settled.length === 1 ? "plan" : "plans"}
          </summary>
          <ul className="mt-3 space-y-1 text-sm">
            {settled.map((draft) => (
              <li key={draft.id} className="flex items-center justify-between gap-3">
                <span>{draft.title?.trim() || "Untitled plan"}</span>
                <span className="pill pill-muted">{draft.status}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
