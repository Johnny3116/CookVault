"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { apiFetch } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { RecipeDraftDetail } from "@/types";

type Mode = "url" | "video" | "paste";

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
      const request: Record<Mode, [string, object]> = {
        url: ["/import", { url: url.trim(), source_title: sourceTitle.trim() || null }],
        // The video's own title is used unless one is given here, so this box
        // means something different in this mode -- see its label below.
        video: ["/import/video", { url: url.trim(), title: sourceTitle.trim() || null }],
        paste: ["/import/paste", { text, source_title: sourceTitle.trim() || null }],
      };
      const [path, body] = request[mode];
      const draft = await apiFetch<RecipeDraftDetail>(path, {
        method: "POST",
        body: JSON.stringify(body),
      });
      router.push(`/drafts/${draft.id}`);
    } catch (err) {
      // The backend explains refusals in plain words (a private address, a
      // 404, an empty paste). Show that rather than a stack of JSON.
      setError(describeApiError(err, "Import failed"));
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
        {(["url", "video", "paste"] as Mode[]).map((option) => (
          <button
            key={option}
            onClick={() => setMode(option)}
            aria-pressed={mode === option}
            className={`rounded border px-3 py-1 text-sm ${
              mode === option ? "border-neutral-800 bg-neutral-800 text-white" : "border-neutral-300"
            }`}
          >
            {{ url: "From a web page", video: "From a video", paste: "Paste the text" }[option]}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="space-y-4">
        {mode === "url" || mode === "video" ? (
          <label className="block text-sm">
            <span className="mb-1 block font-medium">
              {mode === "video" ? "Video link" : "Recipe URL"}
            </span>
            <span className="mb-1 block text-xs text-neutral-500">
              {mode === "video" ? (
                <>
                  YouTube, TikTok or Instagram. The description and the spoken transcript are both
                  read and both kept — captions alone routinely miss a third of a recipe. Only the
                  description is turned into ingredients; if it hasn&apos;t got a recipe in it the
                  draft arrives empty with the transcript attached, rather than guessing at speech.
                </>
              ) : (
                <>
                  If the page publishes structured recipe data, the amounts come straight from the
                  publisher. Otherwise the page text is parsed, which is rougher.
                </>
              )}
            </span>
            <input
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder={mode === "video" ? "https://www.youtube.com/watch?v=…" : "https://…"}
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
          <span className="mb-1 block font-medium">
            {mode === "video" ? "Recipe title (optional)" : "Source title (optional)"}
          </span>
          {mode === "video" && (
            <span className="mb-1 block text-xs text-neutral-500">
              Video titles are shoutier than recipe names. Leave blank to keep the video&apos;s own.
            </span>
          )}
          <input
            value={sourceTitle}
            onChange={(e) => setSourceTitle(e.target.value)}
            placeholder={mode === "video" ? "Carbonara" : "Nonna's book, p.42"}
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
