"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { CookLogEntry } from "@/types";

/** "I made this" plus the record of the times you did.
 *
 * The rating and note belong to the occasion rather than to the recipe: "too
 * salty" is a fact about the night you cooked it, and averaging that away
 * would lose the thing the history is for.
 */
export function CookLog({ recipeId, onChange }: { recipeId: string; onChange?: () => void }) {
  const [entries, setEntries] = useState<CookLogEntry[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [rating, setRating] = useState("");

  const load = useCallback(() => {
    apiFetch<CookLogEntry[]>(`/recipes/${recipeId}/history`)
      .then(setEntries)
      .catch((err) => setError(describeApiError(err, "Failed to load history")));
  }, [recipeId]);

  useEffect(load, [load]);

  async function record() {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/recipes/${recipeId}/cooked`, {
        method: "POST",
        body: JSON.stringify({
          notes: notes.trim() || null,
          rating: rating ? Number(rating) : null,
        }),
      });
      setNotes("");
      setRating("");
      setOpen(false);
      load();
      onChange?.();
    } catch (err) {
      setError(describeApiError(err, "Failed to record"));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setBusy(true);
    try {
      await apiFetch(`/history/${id}`, { method: "DELETE" });
      load();
      onChange?.();
    } catch (err) {
      setError(describeApiError(err, "Failed to delete"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded border border-neutral-200 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Cooking history
        </h2>
        <button
          onClick={() => setOpen((was) => !was)}
          className="rounded bg-neutral-800 px-3 py-1 text-sm text-white"
        >
          {open ? "Cancel" : "I cooked this"}
        </button>
      </div>

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {open && (
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="text-sm">
            <span className="mb-1 block text-xs text-neutral-500">Rating</span>
            <select
              value={rating}
              onChange={(e) => setRating(e.target.value)}
              className="rounded border border-neutral-300 px-2 py-1 text-sm"
            >
              <option value="">—</option>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-48 flex-1 text-sm">
            <span className="mb-1 block text-xs text-neutral-500">
              How did it go? (this time, not forever)
            </span>
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="needed 10 minutes longer"
              className="w-full rounded border border-neutral-300 px-2 py-1 text-sm"
            />
          </label>
          <button
            onClick={record}
            disabled={busy}
            className="rounded bg-neutral-800 px-3 py-1 text-sm text-white disabled:opacity-50"
          >
            Record
          </button>
        </div>
      )}

      {entries.length === 0 ? (
        <p className="mt-3 text-sm text-neutral-500">Never cooked.</p>
      ) : (
        <ul className="mt-3 space-y-1 text-sm">
          {entries.map((entry) => (
            <li key={entry.id} className="group flex items-baseline gap-2">
              <span className="tabular-nums text-neutral-600">{entry.cooked_on}</span>
              {entry.rating && <span className="text-amber-600">{"★".repeat(entry.rating)}</span>}
              {entry.notes && <span className="flex-1 text-neutral-500">{entry.notes}</span>}
              <button
                onClick={() => remove(entry.id)}
                aria-label={`Remove entry from ${entry.cooked_on}`}
                className="ml-auto text-xs text-neutral-300 hover:text-red-600 group-hover:text-neutral-400"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
