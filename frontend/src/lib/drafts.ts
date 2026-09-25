import type { DraftStatus } from "@/types";

/** Status pill classes, shared by the queue and the draft page. */
export const STATUS_PILL: Record<DraftStatus, string> = {
  draft: "pill pill-muted",
  ready: "pill pill-mint",
  promoted: "pill pill-sky",
  discarded: "pill pill-muted opacity-60",
};
