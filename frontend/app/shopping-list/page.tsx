"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { addDays, fmtDate, startOfWeek } from "@/lib/dates";
import { ingredientLabel } from "@/lib/format";
import { AISLES } from "@/types";
import type { IngredientCategory, RecipeSummary, ShoppingListItem } from "@/types";

const CATEGORIES: { key: IngredientCategory; label: string }[] = [
  { key: "raw_ingredient", label: "Raw Ingredients" },
  { key: "spice_sauce", label: "Spices & Sauces" },
  { key: "pantry_dry_good", label: "Pantry & Dry Goods" },
  { key: "misc", label: "Misc" },
];

const input = "rounded border border-neutral-300 px-3 py-2 text-sm";

export default function ShoppingListPage() {
  const [items, setItems] = useState<ShoppingListItem[]>([]);
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [draft, setDraft] = useState({
    name: "",
    quantity: "",
    unit: "",
    category: "misc" as IngredientCategory,
  });
  const [weekOffset, setWeekOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setItems(await apiFetch<ShoppingListItem[]>("/shopping-list"));
  }, []);

  useEffect(() => {
    load().catch(() => {});
    apiFetch<RecipeSummary[]>("/recipes").then(setRecipes).catch(() => {});
  }, [load]);

  async function run(work: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await work();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  function toggleRecipe(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const checkedCount = items.filter((i) => i.is_checked).length;

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Shopping List</h1>

      <section className="rounded border border-neutral-200 p-4">
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Build from this week's plan
        </h2>
        <p className="mb-3 text-xs text-neutral-500">
          Buys the servings actually planned for each day, scaling each recipe from its own yield.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => {
              const start = startOfWeek(weekOffset === 0 ? new Date() : addDays(new Date(), weekOffset * 7));
              run(() =>
                apiFetch("/shopping-list/generate", {
                  method: "POST",
                  body: JSON.stringify({
                    start: fmtDate(start),
                    end: fmtDate(addDays(start, 6)),
                  }),
                }),
              );
            }}
            disabled={busy}
            className="rounded bg-neutral-800 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            Generate from {weekOffset === 0 ? "this week" : "next week"}
          </button>
          <select
            value={weekOffset}
            onChange={(e) => setWeekOffset(Number(e.target.value))}
            aria-label="Which week"
            className="rounded border border-neutral-300 px-3 py-2 text-sm"
          >
            <option value={0}>This week</option>
            <option value={1}>Next week</option>
          </select>
        </div>
      </section>

      <section className="rounded border border-neutral-200 p-4">
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Or build from specific recipes
        </h2>
        <p className="mb-3 text-xs text-neutral-500">
          Duplicate ingredients are combined. Generating again replaces these rows and leaves
          anything you added by hand alone.
        </p>
        {recipes.length === 0 ? (
          <p className="text-sm text-neutral-400">No recipes saved yet.</p>
        ) : (
          <>
            <div className="max-h-48 space-y-1 overflow-y-auto">
              {recipes.map((recipe) => (
                <label key={recipe.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selected.has(recipe.id)}
                    onChange={() => toggleRecipe(recipe.id)}
                  />
                  {recipe.title}
                </label>
              ))}
            </div>
            <button
              onClick={() =>
                run(() =>
                  apiFetch("/shopping-list/generate", {
                    method: "POST",
                    body: JSON.stringify({ recipe_ids: [...selected] }),
                  }),
                )
              }
              disabled={busy}
              className="mt-3 rounded bg-neutral-800 px-4 py-2 text-sm text-white disabled:opacity-50"
            >
              {selected.size === 0 ? "Clear generated items" : `Generate from ${selected.size}`}
            </button>
          </>
        )}
      </section>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!draft.name.trim()) return;
          run(async () => {
            await apiFetch("/shopping-list", {
              method: "POST",
              body: JSON.stringify({
                name: draft.name.trim(),
                quantity: draft.quantity ? Number(draft.quantity) : null,
                unit: draft.unit.trim() || null,
                category: draft.category,
              }),
            });
            setDraft({ name: "", quantity: "", unit: "", category: draft.category });
          });
        }}
        className="flex flex-wrap gap-2"
      >
        <input
          placeholder="qty"
          inputMode="decimal"
          value={draft.quantity}
          onChange={(e) => setDraft({ ...draft, quantity: e.target.value })}
          className={`w-16 ${input}`}
        />
        <input
          placeholder="unit"
          value={draft.unit}
          onChange={(e) => setDraft({ ...draft, unit: e.target.value })}
          className={`w-20 ${input}`}
        />
        <input
          placeholder="Add an item"
          value={draft.name}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          className={`flex-1 ${input}`}
        />
        <select
          aria-label="Category"
          value={draft.category}
          onChange={(e) => setDraft({ ...draft, category: e.target.value as IngredientCategory })}
          className={input}
        >
          {CATEGORIES.map((c) => (
            <option key={c.key} value={c.key}>
              {c.label}
            </option>
          ))}
        </select>
        <button type="submit" disabled={busy} className="rounded bg-neutral-800 px-4 py-2 text-sm text-white disabled:opacity-50">
          Add
        </button>
      </form>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex items-center gap-3 text-sm">
        <span className="text-neutral-500">
          {items.length} item{items.length === 1 ? "" : "s"}
          {checkedCount > 0 && `, ${checkedCount} checked`}
        </span>
        <button
          onClick={() => run(() => apiFetch("/shopping-list?checked_only=true", { method: "DELETE" }))}
          disabled={busy || checkedCount === 0}
          className="underline disabled:opacity-40"
        >
          Clear checked
        </button>
        <button
          onClick={() => {
            if (window.confirm("Clear the entire shopping list?")) {
              run(() => apiFetch("/shopping-list", { method: "DELETE" }));
            }
          }}
          disabled={busy || items.length === 0}
          className="underline disabled:opacity-40"
        >
          Clear all
        </button>
      </div>

      {/* Grouped by aisle rather than by ingredient category: this list is
          used while walking a shop, and only aisles with something in them
          are shown -- nine empty headings is noise, not structure. */}
      <div className="space-y-6">
        {AISLES.filter((aisle) => items.some((i) => i.aisle === aisle.key)).map((aisle) => {
          const inAisle = items.filter((i) => i.aisle === aisle.key);
          return (
            <div key={aisle.key}>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
                {aisle.label}
              </h3>
              <ul className="space-y-1">
                {inAisle.map((item) => (
                  <li key={item.id} className="group flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={item.is_checked}
                      aria-label={item.name}
                      onChange={() =>
                        run(() =>
                          apiFetch(`/shopping-list/${item.id}`, {
                            method: "PATCH",
                            body: JSON.stringify({ is_checked: !item.is_checked }),
                          }),
                        )
                      }
                    />
                    <span className={`${item.is_checked ? "text-neutral-400 line-through" : ""}`}>
                      {ingredientLabel(item)}
                    </span>
                    {/* A hint, not a subtraction: the line is still on the
                        list, because dropping it would silently under-buy. */}
                    {item.in_pantry && (
                      <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-500">
                        in pantry
                      </span>
                    )}
                    <span className="flex-1" />
                    {/* Moving a line is per-item, and "auto" hands it back to
                        the rules rather than pinning it where it happens to
                        be now. */}
                    <select
                      aria-label={`Aisle for ${item.name}`}
                      value={item.aisle_override ?? ""}
                      onChange={(e) =>
                        run(() =>
                          apiFetch(`/shopping-list/${item.id}`, {
                            method: "PATCH",
                            body: JSON.stringify({ aisle_override: e.target.value || null }),
                          }),
                        )
                      }
                      className="rounded border-none bg-transparent text-xs text-neutral-300 hover:text-neutral-600 focus:text-neutral-700 group-hover:text-neutral-400"
                    >
                      <option value="">auto</option>
                      {AISLES.map((option) => (
                        <option key={option.key} value={option.key}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => run(() => apiFetch(`/shopping-list/${item.id}`, { method: "DELETE" }))}
                      aria-label={`Remove ${item.name}`}
                      className="text-xs text-neutral-300 hover:text-red-600 group-hover:text-neutral-400"
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
        {items.length === 0 && <p className="text-sm text-neutral-400">Nothing on the list.</p>}
      </div>
    </div>
  );
}
