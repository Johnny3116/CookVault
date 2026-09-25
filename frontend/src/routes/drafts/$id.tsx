import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorText, PageHeader } from "@/components/PageHeader";
import { ProvenanceCard } from "@/components/ProvenanceCard";
import { RecipeForm, type RecipeFormInitial, type RecipePayload } from "@/components/RecipeForm";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch, json } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import { STATUS_PILL } from "@/lib/drafts";
import type { DraftValidation, RecipeDetail, RecipeDraftDetail } from "@/types";

export const Route = createFileRoute("/drafts/$id")({
  component: DraftPage,
});

/** A refusal-to-promote body, or null if this 422 is some other shape. */
function parseValidation(err: unknown): DraftValidation | null {
  if (!(err instanceof ApiError) || err.status !== 422) return null;
  try {
    const detail = JSON.parse(err.body).detail;
    return detail && Array.isArray(detail.issues) ? (detail as DraftValidation) : null;
  } catch {
    return null;
  }
}

function DraftPage() {
  const { id } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [validation, setValidation] = useState<DraftValidation | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const draftQuery = useQuery({ queryKey: ["draft", id], queryFn: () => apiFetch<RecipeDraftDetail>(`/drafts/${id}`) });
  const draft = draftQuery.data;

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["draft", id] });
    queryClient.invalidateQueries({ queryKey: ["drafts"] });
  };

  async function handleSave(payload: RecipePayload) {
    await apiFetch(`/drafts/${id}`, json("PATCH", { title: payload.title, payload }));
    // The saved payload has not been checked, so any previous verdict is about
    // a payload that no longer exists. Showing it would be a lie.
    setValidation(null);
    setSaved(true);
    refresh();
  }

  const validate = useMutation({
    mutationFn: () => apiFetch<DraftValidation>(`/drafts/${id}/validate`, { method: "POST" }),
    onSuccess: (result) => {
      setValidation(result);
      setError(null);
      refresh();
    },
    onError: (err) => setError(describeApiError(err)),
  });

  const promote = useMutation({
    mutationFn: () => apiFetch<RecipeDetail>(`/drafts/${id}/promote`, { method: "POST" }),
    onSuccess: (recipe) => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
      refresh();
      toast.success(`${recipe.title} is in the cookbook.`);
      navigate({ to: "/recipes/$id", params: { id: recipe.id } });
    },
    onError: (err) => {
      // A refused promotion is the system doing its job, so show the reasons
      // rather than a wall of JSON.
      const detail = parseValidation(err);
      if (detail) {
        setValidation(detail);
        setError("This draft isn't ready yet — see below.");
      } else {
        setError(describeApiError(err, "Failed to promote"));
      }
    },
  });

  const discard = useMutation({
    mutationFn: () => apiFetch(`/drafts/${id}/discard`, { method: "POST" }),
    onSuccess: refresh,
    onError: (err) => setError(describeApiError(err)),
  });

  const remove = useMutation({
    mutationFn: () => apiFetch(`/drafts/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
      navigate({ to: "/drafts" });
    },
    onError: (err) => setError(describeApiError(err)),
  });

  if (draftQuery.error) return <ErrorText>{describeApiError(draftQuery.error, "Failed to load draft")}</ErrorText>;
  if (!draft) return <div className="glass-panel p-10 text-center text-muted-foreground">Loading…</div>;

  const settled = draft.status === "promoted" || draft.status === "discarded";
  const busy = validate.isPending || promote.isPending || discard.isPending || remove.isPending;
  const errors = validation?.issues.filter((i) => i.severity === "error") ?? [];
  const warnings = validation?.issues.filter((i) => i.severity === "warning") ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Draft"
        title={draft.title?.trim() || "Untitled draft"}
        intro={
          <span className="inline-flex flex-wrap items-center gap-2">
            <span className={STATUS_PILL[draft.status]}>{draft.status}</span>
            {draft.status === "ready" && "validated, waiting on you"}
            {draft.created_by === "agent" && <span className="pill pill-honey">proposed by Sage</span>}
          </span>
        }
        actions={
          <>
            <Button asChild variant="secondary" className="glass-button">
              <Link to="/drafts">All drafts</Link>
            </Button>
            {!settled && (
              <>
                <Button variant="secondary" className="glass-button" onClick={() => validate.mutate()} disabled={busy}>
                  Validate
                </Button>
                <Button onClick={() => promote.mutate()} disabled={busy}>
                  Promote to recipe
                </Button>
                <Button variant="secondary" className="glass-button" onClick={() => discard.mutate()} disabled={busy}>
                  Discard
                </Button>
                <Button
                  variant="destructive"
                  disabled={busy}
                  onClick={() => {
                    if (window.confirm("Delete this draft outright? Discard keeps the record instead.")) remove.mutate();
                  }}
                >
                  Delete
                </Button>
              </>
            )}
          </>
        }
      />

      {/* What the proposer was unsure about, addressed to the reviewer. It
          never becomes part of the recipe. */}
      {draft.note && <div className="draft-card">{draft.note}</div>}

      <ErrorText>{error}</ErrorText>
      {saved && !validation && (
        <p className="text-sm text-muted-foreground">Saved. Validate again when you want to know whether it is promotable.</p>
      )}

      {validation && (
        <section className="glass-panel space-y-3 p-5">
          <p className="text-sm font-semibold">
            {validation.ok
              ? warnings.length > 0
                ? "No blocking problems, but worth a look:"
                : "No problems found. This draft can be promoted."
              : "Not promotable yet:"}
          </p>
          {errors.length > 0 && (
            <ul className="space-y-1 text-sm text-destructive">
              {errors.map((issue, index) => (
                <li key={`e${index}`}>
                  <code className="text-xs">{issue.field}</code> {issue.message}
                </li>
              ))}
            </ul>
          )}
          {warnings.length > 0 && (
            <ul className="space-y-1 text-sm" style={{ color: "oklch(0.5 0.13 75)" }}>
              {warnings.map((issue, index) => (
                <li key={`w${index}`}>
                  <code className="text-xs">{issue.field}</code> {issue.message}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {draft.provenance && <ProvenanceCard provenance={draft.provenance} />}

      {settled ? (
        <section className="glass-panel p-5">
          <p className="text-sm text-muted-foreground">
            {draft.status === "promoted" ? (
              <>
                Promoted{draft.promoted_at ? ` on ${new Date(draft.promoted_at).toLocaleString()}` : ""}. This draft is kept as the
                record of what was approved.{" "}
                {draft.promoted_recipe_id && (
                  <Link to="/recipes/$id" params={{ id: draft.promoted_recipe_id }} className="text-primary underline">
                    Open the recipe
                  </Link>
                )}
              </>
            ) : (
              "Discarded. Kept as the record of having rejected it."
            )}
          </p>
          <pre className="source-pre">{JSON.stringify(draft.payload, null, 2)}</pre>
        </section>
      ) : (
        <RecipeForm key={draft.updated_at} initial={draft.payload as RecipeFormInitial} submitLabel="Save draft" onSubmit={handleSave} />
      )}
    </div>
  );
}
