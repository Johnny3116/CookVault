"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import type { RecipeDraftDetail } from "@/types";

type Mode = "url" | "paste";

export default function ImportPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("url");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [sourceTitle, setSourceTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const draft =
        mode === "url"
          ? await apiFetch<RecipeDraftDetail>("/import", {
              method: "POST",
              body: JSON.stringify({
                url: url.trim(),
                source_title: sourceTitle.trim() || null,
              }),
            })
          : await apiFetch<RecipeDraftDetail>("/import/paste", {
              method: "POST",
              body: JSON.stringify({
                text,
                source_title: sourceTitle.trim() || null,
              }),
            });
      router.push(`/drafts/${draft.id}`);
    } catch (err) {
      // The backend explains refusals in plain words (a private address, a
      // 404, an empty paste). Show that rather than a stack of JSON.
      if (err instanceof ApiError) {
        try {
          setError(JSON.parse(err.body).detail ?? err.message);
        } catch {
          setError(err.message);
        }
      } else {
        setError(err instanceof Error ? err.message : "Import failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Import a recipe</h1>
        <p className="mt-1 max-w-2xl text-sm text-neutral-500">
          Anything imported lands in a draft, never straight in the cookbook — an importer reads
          text somebody else wrote and is sometimes wrong about it. You will see what it made of
          the source, and what the source said, before anything counts.
        </p>
      </div>

      <div className="flex gap-2">
        {(["url", "paste"] as Mode[]).map((option) => (
          <button
            key={option}
            onClick={() => setMode(option)}
            aria-pressed={mode === option}
            className={`rounded border px-3 py-1 text-sm ${
              mode === option ? "border-neutral-800 bg-neutral-800 text-white" : "border-neutral-300"
            }`}
          >
            {option === "url" ? "From a web page" : "Paste the text"}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="space-y-4">
        {mode === "url" ? (
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Recipe URL</span>
            <span className="mb-1 block text-xs text-neutral-500">
              If the page publishes structured recipe data, the amounts come straight from the
              publisher. Otherwise the page text is parsed, which is rougher.
            </span>
            <input
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://…"
              className="w-full rounded border border-neutral-300 px-2 py-1"
            />
          </label>
        ) : (
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Recipe text</span>
            <span className="mb-1 block text-xs text-neutral-500">
              Ingredients one per line. `Ingredients:` and `Method:` headings are used if present.
            </span>
            <textarea
              required
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={14}
              placeholder={"Mushroom Risotto\nServes 4\n\nIngredients:\n1 1/2 cups arborio rice\n…"}
              className="w-full rounded border border-neutral-300 px-2 py-1 font-mono text-xs"
            />
          </label>
        )}

        <label className="block text-sm">
          <span className="mb-1 block font-medium">Source title (optional)</span>
          <input
            value={sourceTitle}
            onChange={(e) => setSourceTitle(e.target.value)}
            placeholder="Nonna's book, p.42"
            className="w-full rounded border border-neutral-300 px-2 py-1"
          />
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="rounded bg-neutral-800 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {busy ? "Importing…" : "Import to a draft"}
        </button>
      </form>
    </div>
  );
}
