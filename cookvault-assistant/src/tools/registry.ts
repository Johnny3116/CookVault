import { z } from "zod";

import type { CookVaultClient } from "../cookvault.ts";
import type { ToolSpec } from "../provider/types.ts";
import type { ToolLink } from "../sse.ts";

/** What a tool may do. Enforced server-side: the model cannot change it.
 *
 * READ executes on request. WRITE_DRAFT creates something reviewable and
 * nothing else -- every write on this service is a draft, which is what
 * CookVault's /agent surface allows and all it allows. There is no WRITE and
 * no DESTRUCTIVE tool, by construction rather than by policy.
 */
export type ToolKind = "READ" | "WRITE_DRAFT";

export interface ToolContext {
  cookvault: CookVaultClient;
  model: string;
  version: string;
  /** Today, as YYYY-MM-DD, so tools can default date windows sensibly. */
  today: string;
}

export interface ToolResult {
  /** What the model sees. Keep it small: it is tokens in a shared context. */
  content: unknown;
  /** One short phrase for the UI chip, e.g. "3 recipes". */
  summary?: string;
  /** Things the UI can link to: a draft to review, a recipe to open. */
  links?: ToolLink[];
  /** For the audit log: the id of whatever was created. */
  affectedId?: string;
}

export interface Tool<I = unknown> {
  name: string;
  description: string;
  kind: ToolKind;
  schema: z.ZodType<I>;
  /** What the UI shows while it runs, e.g. "Searching your recipes…". */
  label: (args: I) => string;
  execute: (args: I, ctx: ToolContext) => Promise<ToolResult>;
}

export class ToolRegistry {
  private readonly tools = new Map<string, Tool<any>>();

  register<I>(tool: Tool<I>): this {
    if (this.tools.has(tool.name)) throw new Error(`tool ${tool.name} registered twice`);
    this.tools.set(tool.name, tool);
    return this;
  }

  get(name: string): Tool | undefined {
    return this.tools.get(name);
  }

  names(): string[] {
    return [...this.tools.keys()];
  }

  /** The list the model is shown, generated from the same schemas that
   *  validate its arguments, so the two cannot disagree. */
  specs(): ToolSpec[] {
    return [...this.tools.values()].map((tool) => ({
      name: tool.name,
      description: tool.description,
      parameters: jsonSchemaFor(tool.schema),
    }));
  }
}

/** Zod -> JSON Schema, flattened for a small local model.
 *
 * Optionality is carried by `required`, so no `anyOf: [T, null]` unions --
 * the eval harness under backend/evals found small models read those badly.
 * The schemas below avoid `.nullable()` for the same reason.
 */
export function jsonSchemaFor(schema: z.ZodType): Record<string, unknown> {
  const raw = z.toJSONSchema(schema, { target: "draft-7", io: "input" }) as Record<string, unknown>;
  delete raw["$schema"];
  return strip(raw) as Record<string, unknown>;
}

function strip(node: unknown): unknown {
  if (Array.isArray(node)) return node.map(strip);
  if (!node || typeof node !== "object") return node;
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(node as Record<string, unknown>)) {
    // A default invites the model to send it explicitly; a title repeats the key.
    if (key === "default" || key === "title") continue;
    // `.int()` emits the safe-integer bounds, which say nothing to a model.
    if ((key === "maximum" || key === "minimum") && Math.abs(Number(value)) === Number.MAX_SAFE_INTEGER) continue;
    out[key] = strip(value);
  }
  return out;
}
