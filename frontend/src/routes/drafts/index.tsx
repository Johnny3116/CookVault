import { useQuery } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import { Bot } from "lucide-react";
import { useState } from "react";

import { EmptyState, ErrorText, PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { STATUS_PILL } from "@/lib/drafts";
import { describeApiError } from "@/lib/errors";
import type { DraftStatus, RecipeDraftSummary } from "@/types";

const FILTERS: { value: DraftStatus | "all"; label: string }[] = [
  { value: "draft", label: "In progress" },
  { value: "ready", label: "Ready to review" },
  { value: "promoted", label: "Promoted" },
  { value: "discarded", label: "Discarded" },
  { value: "all", label: "All" },
];

export const Route = createFileRoute("/drafts/")({
  head: () => ({ meta: [{ title: "Drafts — CookVault" }] }),
  component: DraftsPage,
});

function DraftsPage() {
  // The default view is the work queue, not the archive: promoted and
  // discarded drafts are finished business.
  const [filter, setFilter] = useState<DraftStatus | "all">("draft");
  const drafts = useQuery({
    queryKey: ["drafts", filter],
    queryFn: () => apiFetch<RecipeDraftSummary[]>(`/drafts${filter === "all" ? "" : `?status_filter=${filter}`}`),
  });

  return (
    <div>
      <PageHeader
        eyebrow="Review queue"
        title="Drafts"
        intro="Proposed recipes waiting on you. Nothing here is in the cookbook until it passes validation and you promote it."
        actions={
          <>
            <Button asChild variant="secondary" className="glass-button">
              <Link to="/drafts/import">Import</Link>
            </Button>
            <Button asChild>
              <Link to="/drafts/new">New draft</Link>
            </Button>
          </>
        }
      />

      <div className="chip-row mb-5">
        {FILTERS.map((option) => (
          <button key={option.value} className="chip" aria-pressed={filter === option.value} onClick={() => setFilter(option.value)}>
            {option.label}
          </button>
        ))}
      </div>

      {drafts.error && <ErrorText>{describeApiError(drafts.error)}</ErrorText>}

      {drafts.data && drafts.data.length === 0 ? (
        <EmptyState title="Nothing here">The queue is clear. Import something, or ask ChefNexus to draft a recipe.</EmptyState>
      ) : (
        <div className="glass-panel p-2 sm:p-4">
          <ul className="list-rows">
            {(drafts.data ?? []).map((draft) => (
              <li key={draft.id} className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <Link to="/drafts/$id" params={{ id: draft.id }} className="font-display text-lg font-semibold hover:underline">
                    {draft.title?.trim() || "Untitled draft"}
                  </Link>
                  <p className="text-xs text-muted-foreground">updated {new Date(draft.updated_at).toLocaleString()}</p>
                  {/* The note is what the proposer wanted to say to the
                      reviewer -- the reason to open this one first. */}
                  {draft.note && <p className="mt-1 max-w-xl text-xs italic text-muted-foreground">{draft.note}</p>}
                </div>
                <div className="flex items-center gap-2">
                  {draft.created_by === "agent" && (
                    <span className="pill pill-honey">
                      <Bot className="size-3" /> proposed by ChefNexus
                    </span>
                  )}
                  <span className={STATUS_PILL[draft.status]}>{draft.status}</span>
                  {draft.promoted_recipe_id && (
                    <Link to="/recipes/$id" params={{ id: draft.promoted_recipe_id }} className="text-xs text-primary underline">
                      view recipe
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
