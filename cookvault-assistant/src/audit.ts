import { appendFile, mkdir } from "node:fs/promises";
import { dirname } from "node:path";

import { log } from "./log.ts";

/** One line per tool call, so a draft that appeared in the queue can be
 *  traced back to the conversation, the model and the arguments that made it.
 *  Arguments are the validated ones, not what the model first said; secrets
 *  never pass through here because tools never see any. */
export interface AuditEntry {
  ts: string;
  conversation_id: string;
  model: string;
  tool: string;
  kind: "READ" | "WRITE_DRAFT";
  arguments: unknown;
  ok: boolean;
  duration_ms: number;
  affected_record_id?: string;
  error?: string;
}

export interface AuditLog {
  record(entry: Omit<AuditEntry, "ts">): Promise<void>;
}

export function createFileAuditLog(path: string): AuditLog {
  let ready: Promise<void> | undefined;
  return {
    async record(entry) {
      ready ??= mkdir(dirname(path), { recursive: true }).then(() => undefined);
      try {
        await ready;
        await appendFile(path, `${JSON.stringify({ ts: new Date().toISOString(), ...entry })}\n`);
      } catch (err) {
        // An audit line that cannot be written is logged, not swallowed --
        // but it does not fail the tool call, which already happened.
        log("error", "audit", "could not append audit entry", { path, error: String(err) });
      }
    },
  };
}

export function createMemoryAuditLog(): AuditLog & { entries: AuditEntry[] } {
  const entries: AuditEntry[] = [];
  return {
    entries,
    async record(entry) {
      entries.push({ ts: new Date().toISOString(), ...entry });
    },
  };
}
