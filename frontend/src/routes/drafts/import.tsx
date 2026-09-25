import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { ErrorText, PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { apiFetch, json } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { RecipeDraftDetail } from "@/types";

type Mode = "url" | "video" | "paste";

const MODES: { value: Mode; label: string }[] = [
  { value: "url", label: "From a web page" },
  { value: "video", label: "From a video" },
  { value: "paste", label: "Paste the text" },
];

export const Route = createFileRoute("/drafts/import")({
  head: () => ({ meta: [{ title: "Import — CookVault" }] }),
  component: ImportPage,
});

function ImportPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<Mode>("url");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [sourceTitle, setSourceTitle] = useState("");

  const importDraft = useMutation({
    mutationFn: () => {
      const request: Record<Mode, [string, object]> = {
        url: ["/import", { url: url.trim(), source_title: sourceTitle.trim() || null }],
        // The video's own title is used unless one is given here.
        video: ["/import/video", { url: url.trim(), title: sourceTitle.trim() || null }],
        paste: ["/import/paste", { text, source_title: sourceTitle.trim() || null }],
      };
      const [path, body] = request[mode];
      return apiFetch<RecipeDraftDetail>(path, json("POST", body));
    },
    onSuccess: (draft) => {
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
      navigate({ to: "/drafts/$id", params: { id: draft.id } });
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Import"
        title="Import a recipe"
        intro="Anything imported lands in a draft, never straight in the cookbook — an importer reads text somebody else wrote and is sometimes wrong about it. You will see what it made of the source, and what the source said, before anything counts."
      />

      <div className="chip-row">
        {MODES.map((option) => (
          <button key={option.value} className="chip" aria-pressed={mode === option.value} onClick={() => setMode(option.value)}>
            {option.label}
          </button>
        ))}
      </div>

      <form
        className="glass-panel editor-form max-w-3xl"
        onSubmit={(e) => {
          e.preventDefault();
          importDraft.mutate();
        }}
      >
        {mode === "paste" ? (
          <label>
            Recipe text
            <span className="field-hint">Ingredients one per line. `Ingredients:` and `Method:` headings are used if present.</span>
            <textarea
              required
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={14}
              placeholder={"Mushroom Risotto\nServes 4\n\nIngredients:\n1 1/2 cups arborio rice\n…"}
              className="field font-mono !text-xs"
            />
          </label>
        ) : (
          <label>
            {mode === "video" ? "Video link" : "Recipe URL"}
            <span className="field-hint">
              {mode === "video"
                ? "YouTube, TikTok or Instagram. The description and the spoken transcript are both read and both kept — captions alone routinely miss a third of a recipe. Only the description is turned into ingredients; if it hasn't got a recipe in it the draft arrives empty with the transcript attached, rather than guessing at speech."
                : "If the page publishes structured recipe data, the amounts come straight from the publisher. Otherwise the page text is parsed, which is rougher."}
            </span>
            <input
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder={mode === "video" ? "https://www.youtube.com/watch?v=…" : "https://…"}
              className="field"
            />
          </label>
        )}

        <label>
          {mode === "video" ? "Recipe title (optional)" : "Source title (optional)"}
          {mode === "video" && <span className="field-hint">Video titles are shoutier than recipe names. Leave blank to keep the video's own.</span>}
          <input value={sourceTitle} onChange={(e) => setSourceTitle(e.target.value)} placeholder={mode === "video" ? "Carbonara" : "Nonna's book, p.42"} className="field" />
        </label>

        {importDraft.error && <ErrorText>{describeApiError(importDraft.error, "Import failed")}</ErrorText>}

        <div className="flex justify-end">
          <Button type="submit" disabled={importDraft.isPending}>
            {importDraft.isPending ? "Importing…" : "Import to a draft"}
          </Button>
        </div>
      </form>
    </div>
  );
}
