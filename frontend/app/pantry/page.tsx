"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import { BackupPanel } from "@/components/BackupPanel";
import type { PantryItem } from "@/types";

export default function PantryPage() {
  const [items, setItems] = useState<PantryItem[]>([]);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    apiFetch<PantryItem[]>("/pantry")
      .then(setItems)
      .catch((err) => setError(describeApiError(err, "Failed to load the pantry")));
  }, []);

  useEffect(load, [load]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      load();
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Pantry</h1>
        <p className="mt-1 max-w-2xl text-sm text-neutral-500">
          The things you keep in. No quantities and no expiry dates on purpose — this is not
          inventory software. Its one job is to mark a shopping line as something you probably
          already have. It never takes anything off the list.
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!name.trim()) return;
          run(async () => {
            await apiFetch("/pantry", {
              method: "POST",
              body: JSON.stringify({ name: name.trim(), note: note.trim() || null }),
            });
            setName("");
            setNote("");
          });
        }}
        className="flex flex-wrap gap-2"
      >
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="olive oil"
          aria-label="Pantry item"
          className="min-w-48 flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
        />
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="note (optional)"
          aria-label="Note"
          className="min-w-48 flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-neutral-800 px-4 py-1 text-sm text-white disabled:opacity-50"
        >
          Add
        </button>
      </form>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <BackupPanel />

      {items.length === 0 ? (
        <p className="text-sm text-neutral-500">Nothing in the pantry yet.</p>
      ) : (
        <ul className="divide-y divide-neutral-200 rounded border border-neutral-200">
          {items.map((item) => (
            <li key={item.id} className="group flex items-center gap-3 p-2 text-sm">
              <span className="font-medium">{item.name}</span>
              {item.note && <span className="text-neutral-500">{item.note}</span>}
              <button
                onClick={() => run(() => apiFetch(`/pantry/${item.id}`, { method: "DELETE" }))}
                aria-label={`Remove ${item.name}`}
                className="ml-auto text-xs text-neutral-300 hover:text-red-600 group-hover:text-neutral-400"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
