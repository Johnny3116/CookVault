import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Check, X } from "lucide-react";
import { useState } from "react";

import { ErrorText, PageHeader, SectionHeading } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { apiFetch, json } from "@/lib/api";
import { addDays, fmtDate, startOfWeek } from "@/lib/dates";
import { describeApiError } from "@/lib/errors";
import { ingredientLabel } from "@/lib/format";
import { COLUMNS } from "@/lib/recipes";
import { AISLES } from "@/types";
import type { IngredientCategory, RecipeSummary, ShoppingListItem } from "@/types";

export const Route = createFileRoute("/shopping-list")({
  head: () => ({ meta: [{ title: "Shopping — CookVault" }] }),
  component: ShoppingListPage,
});

function ShoppingListPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [weekOffset, setWeekOffset] = useState(0);
  const [draft, setDraft] = useState({ name: "", quantity: "", unit: "", category: "misc" as IngredientCategory });
  const [error, setError] = useState<string | null>(null);

  const items = useQuery({ queryKey: ["shopping-list"], queryFn: () => apiFetch<ShoppingListItem[]>("/shopping-list") });
  const recipes = useQuery({ queryKey: ["recipes"], queryFn: () => apiFetch<RecipeSummary[]>("/recipes") });

  const mutation = useMutation({
    mutationFn: (work: () => Promise<unknown>) => work(),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
    },
    onError: (err) => setError(describeApiError(err)),
  });
  const run = (work: () => Promise<unknown>) => mutation.mutate(work);
  const busy = mutation.isPending;

  const list = items.data ?? [];
  const checkedCount = list.filter((i) => i.is_checked).length;
  const weekStart = startOfWeek(addDays(new Date(), weekOffset * 7));

  return (
    <div>
      <PageHeader eyebrow="Shopping" title="Shopping list" intro="Grouped by aisle, the way a shop is walked. Generated lines are replaced on the next generate; anything you add by hand stays." />

      <div className="grid gap-6 lg:grid-cols-[2fr_3fr]">
        <div className="space-y-4">
          <section className="glass-panel p-5">
            <h2 className="font-display text-xl font-semibold">Build from the plan</h2>
            <p className="mt-1 text-sm text-muted-foreground">Buys the servings actually planned for each day, scaling each recipe from its own yield.</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <select value={weekOffset} onChange={(e) => setWeekOffset(Number(e.target.value))} aria-label="Which week" className="field field-sm w-auto">
                <option value={0}>This week</option>
                <option value={1}>Next week</option>
              </select>
              <Button
                disabled={busy}
                onClick={() =>
                  run(() =>
                    apiFetch("/shopping-list/generate", json("POST", { start: fmtDate(weekStart), end: fmtDate(addDays(weekStart, 6)) })),
                  )
                }
              >
                Generate from {weekOffset === 0 ? "this week" : "next week"}
              </Button>
            </div>
          </section>

          <section className="glass-panel p-5">
            <h2 className="font-display text-xl font-semibold">Or from specific recipes</h2>
            <p className="mt-1 text-sm text-muted-foreground">Duplicate ingredients are combined where the units allow.</p>
            {(recipes.data ?? []).length === 0 ? (
              <p className="mt-3 text-sm text-muted-foreground">No recipes saved yet.</p>
            ) : (
              <>
                <div className="mt-3 max-h-56 space-y-1 overflow-y-auto pr-1">
                  {recipes.data!.map((recipe) => (
                    <label key={recipe.id} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={selected.has(recipe.id)}
                        onChange={() =>
                          setSelected((prev) => {
                            const next = new Set(prev);
                            if (next.has(recipe.id)) next.delete(recipe.id);
                            else next.add(recipe.id);
                            return next;
                          })
                        }
                        className="size-4 accent-[oklch(0.72_0.17_160)]"
                      />
                      {recipe.title}
                    </label>
                  ))}
                </div>
                <Button
                  variant="secondary"
                  className="glass-button mt-3"
                  disabled={busy}
                  onClick={() => run(() => apiFetch("/shopping-list/generate", json("POST", { recipe_ids: [...selected] })))}
                >
                  {selected.size === 0 ? "Clear generated items" : `Generate from ${selected.size}`}
                </Button>
              </>
            )}
          </section>

          <form
            className="glass-panel flex flex-wrap gap-2 p-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (!draft.name.trim()) return;
              run(async () => {
                await apiFetch(
                  "/shopping-list",
                  json("POST", {
                    name: draft.name.trim(),
                    quantity: draft.quantity ? Number(draft.quantity) : null,
                    unit: draft.unit.trim() || null,
                    category: draft.category,
                  }),
                );
                setDraft({ name: "", quantity: "", unit: "", category: draft.category });
              });
            }}
          >
            <input placeholder="qty" inputMode="decimal" aria-label="Quantity" value={draft.quantity} onChange={(e) => setDraft({ ...draft, quantity: e.target.value })} className="field field-sm w-16" />
            <input placeholder="unit" aria-label="Unit" value={draft.unit} onChange={(e) => setDraft({ ...draft, unit: e.target.value })} className="field field-sm w-20" />
            <input placeholder="Add an item" aria-label="Item" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} className="field field-sm min-w-32 flex-1" />
            <select aria-label="Category" value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value as IngredientCategory })} className="field field-sm w-auto">
              {COLUMNS.map((c) => (
                <option key={c.category} value={c.category}>
                  {c.label}
                </option>
              ))}
            </select>
            <Button type="submit" size="sm" disabled={busy}>
              Add
            </Button>
          </form>
        </div>

        <div>
          <SectionHeading
            title="The list"
            detail={`${list.length} item${list.length === 1 ? "" : "s"}${checkedCount > 0 ? `, ${checkedCount} checked` : ""}`}
            action={
              <>
                <button className="underline disabled:opacity-40" disabled={busy || checkedCount === 0} onClick={() => run(() => apiFetch("/shopping-list?checked_only=true", { method: "DELETE" }))}>
                  Clear checked
                </button>
                <button
                  className="underline disabled:opacity-40"
                  disabled={busy || list.length === 0}
                  onClick={() => {
                    if (window.confirm("Clear the entire shopping list?")) run(() => apiFetch("/shopping-list", { method: "DELETE" }));
                  }}
                >
                  Clear all
                </button>
              </>
            }
          />
          <ErrorText>{error}</ErrorText>
          <div className="glass-panel mt-3 space-y-6 p-5">
            {list.length === 0 && <p className="text-sm text-muted-foreground">Nothing on the list.</p>}
            {AISLES.filter((aisle) => list.some((i) => i.aisle === aisle.key)).map((aisle) => (
              <div key={aisle.key}>
                <h3 className="eyebrow mb-2">{aisle.label}</h3>
                <ul className="space-y-1.5">
                  {list
                    .filter((i) => i.aisle === aisle.key)
                    .map((item) => (
                      <li key={item.id} className="group flex items-center gap-3 rounded-xl px-1 py-1">
                        <button
                          className={`check-control ${item.is_checked ? "is-checked" : ""}`}
                          aria-label={`${item.is_checked ? "Uncheck" : "Check"} ${item.name}`}
                          onClick={() => run(() => apiFetch(`/shopping-list/${item.id}`, json("PATCH", { is_checked: !item.is_checked })))}
                        >
                          {item.is_checked && <Check />}
                        </button>
                        <span className={`min-w-0 flex-1 text-sm font-medium ${item.is_checked ? "text-muted-foreground line-through" : ""}`}>
                          {ingredientLabel(item)}
                        </span>
                        {item.in_pantry && <span className="pill pill-muted">in pantry</span>}
                        <select
                          aria-label={`Aisle for ${item.name}`}
                          value={item.aisle_override ?? ""}
                          onChange={(e) => run(() => apiFetch(`/shopping-list/${item.id}`, json("PATCH", { aisle_override: e.target.value || null })))}
                          className="rounded border-none bg-transparent text-xs text-muted-foreground/60 hover:text-foreground focus:text-foreground"
                        >
                          <option value="">auto</option>
                          {AISLES.map((option) => (
                            <option key={option.key} value={option.key}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                        <button onClick={() => run(() => apiFetch(`/shopping-list/${item.id}`, { method: "DELETE" }))} aria-label={`Remove ${item.name}`} className="text-muted-foreground/50 hover:text-destructive">
                          <X className="size-4" />
                        </button>
                      </li>
                    ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
