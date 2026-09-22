"use client";

import { useRef, useState } from "react";

import { apiFetch } from "@/lib/api";
import { describeApiError } from "@/lib/errors";

/** Download the whole library, or put a backup back.
 *
 * Restoring replaces everything, so it asks for the word to be typed. An
 * accidental restore cannot be undone from inside the app: the thing it
 * destroyed is exactly what you would need to undo it.
 */
export function BackupPanel() {
  const fileInput = useRef<HTMLInputElement>(null);
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setBusy(true);
    setError(null);
    try {
      const data = await apiFetch<Record<string, unknown>>("/backup/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `cookvault-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setMessage("Exported.");
    } catch (err) {
      setError(describeApiError(err, "Export failed"));
    } finally {
      setBusy(false);
    }
  }

  async function restore() {
    const file = fileInput.current?.files?.[0];
    if (!file) {
      setError("Choose a backup file first.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const data = JSON.parse(await file.text());
      const result = await apiFetch<{ restored: Record<string, number> }>("/backup/restore", {
        method: "POST",
        body: JSON.stringify({ confirm, data }),
      });
      const total = Object.values(result.restored).reduce((sum, n) => sum + n, 0);
      setMessage(`Restored ${total} rows. Reload to see them.`);
      setConfirm("");
    } catch (err) {
      setError(
        err instanceof SyntaxError
          ? "That file isn't JSON."
          : describeApiError(err, "Restore failed"),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-3 rounded border border-neutral-200 p-4">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Backup
      </h2>

      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={download}
          disabled={busy}
          className="rounded border border-neutral-300 px-3 py-1 text-sm disabled:opacity-50"
        >
          Export everything
        </button>
        <span className="text-xs text-neutral-500">
          Recipes, drafts, provenance, the plan, the list, history, pantry and aisle rules.
        </span>
      </div>

      <div className="space-y-2 border-t border-neutral-200 pt-3">
        <p className="text-xs text-neutral-500">
          Restoring <strong>replaces everything</strong> currently stored. Type{" "}
          <code className="rounded bg-neutral-100 px-1">replace</code> to confirm.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <input ref={fileInput} type="file" accept="application/json" className="text-sm" />
          <input
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="replace"
            aria-label="Type replace to confirm"
            className="w-28 rounded border border-neutral-300 px-2 py-1 text-sm"
          />
          <button
            onClick={restore}
            disabled={busy || confirm !== "replace"}
            className="rounded border border-red-300 px-3 py-1 text-sm text-red-600 disabled:opacity-40"
          >
            Restore
          </button>
        </div>
      </div>

      {message && <p className="text-sm text-neutral-600">{message}</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
    </section>
  );
}
