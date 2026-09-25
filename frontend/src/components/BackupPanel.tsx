import { useRef, useState } from "react";

import { ErrorText } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { apiFetch, json } from "@/lib/api";
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
      const result = await apiFetch<{ restored: Record<string, number> }>(
        "/backup/restore",
        json("POST", { confirm, data }),
      );
      const total = Object.values(result.restored).reduce((sum, n) => sum + n, 0);
      setMessage(`Restored ${total} rows. Reload to see them.`);
      setConfirm("");
    } catch (err) {
      setError(err instanceof SyntaxError ? "That file isn't JSON." : describeApiError(err, "Restore failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="glass-panel space-y-4 p-5">
      <div>
        <h2 className="font-display text-xl font-semibold">Backup</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Recipes, drafts, provenance, the plan, the list, history, pantry and aisle rules.
        </p>
      </div>

      <Button variant="secondary" onClick={download} disabled={busy}>
        Export everything
      </Button>

      <div className="space-y-3 border-t border-border pt-4">
        <p className="text-sm text-muted-foreground">
          Restoring <strong className="text-foreground">replaces everything</strong> currently stored. Type{" "}
          <code className="rounded bg-muted px-1">replace</code> to confirm.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <input ref={fileInput} type="file" accept="application/json" className="text-sm" />
          <input
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="replace"
            aria-label="Type replace to confirm"
            className="field w-32"
          />
          <Button variant="destructive" onClick={restore} disabled={busy || confirm !== "replace"}>
            Restore
          </Button>
        </div>
      </div>

      {message && <p className="text-sm text-muted-foreground">{message}</p>}
      <ErrorText>{error}</ErrorText>
    </section>
  );
}
