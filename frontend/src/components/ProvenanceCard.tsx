import type { ImportMethod, Provenance } from "@/types";

// How it arrived, in words rather than as a column value.
const ARRIVAL: Record<ImportMethod, string> = {
  manual: "typed in by hand",
  paste: "pasted text, parsed",
  url_fetch: "fetched from a page",
  video_fetch: "read from a video",
  agent: "proposed by Sage",
};

/** Where a draft or recipe came from, shown read-only.
 *
 * The raw source and the extracted structure are displayed as two separate
 * things because they are stored as two separate things -- "did the transcript
 * actually say two teaspoons, or did the model decide that?" is the question
 * this card exists to let you answer.
 */
export function ProvenanceCard({ provenance }: { provenance: Provenance }) {
  const extracted = provenance.extracted_payload;
  const byAgent = provenance.import_method === "agent";
  // For a video the original text is the transcript, and checking a quantity
  // against what was actually said is the main thing you are here to do -- so
  // it starts open rather than one click away.
  const fromVideo = provenance.import_method === "video_fetch";

  return (
    <section className="glass-panel p-5">
      <h2 className="font-display text-xl font-semibold">Provenance</h2>

      <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="eyebrow !text-[.65rem]">Source</dt>
          <dd className="mt-1">
            {provenance.source_title?.trim() || provenance.source_type}
            {provenance.source_url && (
              <>
                {" "}
                <a href={provenance.source_url} target="_blank" rel="noreferrer" className="text-primary underline">
                  link
                </a>
              </>
            )}
          </dd>
        </div>
        <div>
          <dt className="eyebrow !text-[.65rem]">How it arrived</dt>
          <dd className="mt-1">
            {ARRIVAL[provenance.import_method] ?? provenance.import_method}
            {byAgent && provenance.agent_model && (
              <span className="text-muted-foreground">
                {" "}
                — {provenance.agent_model}
                {provenance.agent_version ? ` ${provenance.agent_version}` : ""}
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt className="eyebrow !text-[.65rem]">Imported</dt>
          <dd className="mt-1">{new Date(provenance.imported_at).toLocaleString()}</dd>
        </div>
      </dl>

      {provenance.original_text && (
        <details className="mt-4" open={fromVideo}>
          <summary className="cursor-pointer text-sm font-semibold">
            {fromVideo ? "Description and transcript" : "Original text"}
          </summary>
          <pre className="source-pre">{provenance.original_text}</pre>
        </details>
      )}

      {extracted && (
        <details className="mt-2">
          <summary className="cursor-pointer text-sm font-semibold">What was extracted from it</summary>
          <p className="mt-1 text-xs text-muted-foreground">
            As first proposed, before any edit. Compare it against the draft to see what you changed.
          </p>
          <pre className="source-pre">{JSON.stringify(extracted, null, 2)}</pre>
        </details>
      )}
    </section>
  );
}
