import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";

import { ErrorText } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { apiFetch, json } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { CookLogEntry } from "@/types";

/** "I made this" plus the record of the times you did.
 *
 * The rating and note belong to the occasion rather than to the recipe: "too
 * salty" is a fact about the night you cooked it, and averaging that away
 * would lose the thing the history is for.
 */
export function CookLog({ recipeId, onChange }: { recipeId: string; onChange?: () => void }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState("");
  const [rating, setRating] = useState("");

  const history = useQuery({
    queryKey: ["history", recipeId],
    queryFn: () => apiFetch<CookLogEntry[]>(`/recipes/${recipeId}/history`),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["history", recipeId] });
    onChange?.();
  };

  const record = useMutation({
    mutationFn: () =>
      apiFetch(
        `/recipes/${recipeId}/cooked`,
        json("POST", { notes: notes.trim() || null, rating: rating ? Number(rating) : null }),
      ),
    onSuccess: () => {
      setNotes("");
      setRating("");
      setOpen(false);
      invalidate();
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => apiFetch(`/history/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });

  const error = record.error ?? remove.error ?? history.error;
  const entries = history.data ?? [];

  return (
    <section className="glass-panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-xl font-semibold">Cooking history</h2>
        <Button size="sm" variant={open ? "secondary" : "default"} onClick={() => setOpen((was) => !was)}>
          {open ? "Cancel" : "I cooked this"}
        </Button>
      </div>

      {error && <div className="mt-3"><ErrorText>{describeApiError(error)}</ErrorText></div>}

      {open && (
        <div className="editor-form mt-3 !p-0 sm:grid-cols-[8rem_1fr_auto] sm:items-end">
          <label>
            Rating
            <select value={rating} onChange={(e) => setRating(e.target.value)} className="field">
              <option value="">—</option>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {"★".repeat(n)}
                </option>
              ))}
            </select>
          </label>
          <label>
            How did it go? (this time, not forever)
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="needed 10 minutes longer"
              className="field"
            />
          </label>
          <Button onClick={() => record.mutate()} disabled={record.isPending}>
            Record
          </Button>
        </div>
      )}

      {entries.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">Never cooked.</p>
      ) : (
        <ul className="mt-3 space-y-1.5 text-sm">
          {entries.map((entry) => (
            <li key={entry.id} className="group flex items-baseline gap-3">
              <span className="tabular-nums text-muted-foreground">{entry.cooked_on}</span>
              {entry.rating && <span className="text-honey">{"★".repeat(entry.rating)}</span>}
              {entry.notes && <span className="flex-1 text-muted-foreground">{entry.notes}</span>}
              <button
                onClick={() => remove.mutate(entry.id)}
                aria-label={`Remove entry from ${entry.cooked_on}`}
                className="ml-auto text-muted-foreground/50 hover:text-destructive"
              >
                <X className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
