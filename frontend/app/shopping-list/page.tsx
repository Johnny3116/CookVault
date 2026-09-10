"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import type { ShoppingListItem } from "@/types";

const CATEGORIES: { key: ShoppingListItem["category"]; label: string }[] = [
  { key: "raw_ingredient", label: "Raw Ingredients" },
  { key: "spice_sauce", label: "Spices & Sauces" },
  { key: "pantry_dry_good", label: "Pantry & Dry Goods" },
  { key: "misc", label: "Misc" },
];

export default function ShoppingListPage() {
  const [items, setItems] = useState<ShoppingListItem[]>([]);
  const [newItemName, setNewItemName] = useState("");

  async function load() {
    setItems(await apiFetch<ShoppingListItem[]>("/shopping-list"));
  }

  useEffect(() => {
    load();
  }, []);

  async function toggleChecked(item: ShoppingListItem) {
    await apiFetch(`/shopping-list/${item.id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_checked: !item.is_checked }),
    });
    load();
  }

  async function addItem(e: React.FormEvent) {
    e.preventDefault();
    if (!newItemName.trim()) return;
    await apiFetch("/shopping-list", {
      method: "POST",
      body: JSON.stringify({ name: newItemName, category: "misc" }),
    });
    setNewItemName("");
    load();
  }

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Shopping List</h1>
      <form onSubmit={addItem} className="flex gap-2">
        <input
          placeholder="Add an item"
          value={newItemName}
          onChange={(e) => setNewItemName(e.target.value)}
          className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm"
        />
        <button type="submit" className="rounded bg-neutral-800 px-4 py-2 text-sm text-white">
          Add
        </button>
      </form>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-4">
        {CATEGORIES.map((cat) => (
          <div key={cat.key}>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">{cat.label}</h3>
            <ul className="space-y-1">
              {items
                .filter((i) => i.category === cat.key)
                .map((item) => (
                  <li key={item.id} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={item.is_checked} onChange={() => toggleChecked(item)} />
                    <span className={item.is_checked ? "text-neutral-400 line-through" : ""}>
                      {item.quantity ? `${item.quantity} ` : ""}
                      {item.unit ? `${item.unit} ` : ""}
                      {item.name}
                    </span>
                  </li>
                ))}
              {items.filter((i) => i.category === cat.key).length === 0 && (
                <li className="text-sm text-neutral-400">—</li>
              )}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
