import { z } from "zod";

import type { Agent } from "./agent.ts";
import type { CookVaultClient } from "./cookvault.ts";
import { log } from "./log.ts";
import type { ChatProvider } from "./provider/types.ts";
import { SSE_HEADERS, encodeSse } from "./sse.ts";

/** The HTTP surface: two routes.
 *
 *   GET  /health   is the model reachable, is CookVault's agent door open
 *   POST /chat     one assistant turn, streamed as server-sent events
 *
 * Nothing here authenticates the caller. The service has no host port; the
 * only way in is the frontend's proxy, which checks John's session cookie
 * against CookVault before forwarding. See frontend/src/routes/api/$.ts.
 */

const turnSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string().max(20_000),
});

const chatBodySchema = z.object({
  conversation_id: z.string().min(1).max(128),
  messages: z.array(turnSchema).min(1).max(200),
});

export interface AppDeps {
  agent: Agent;
  provider: ChatProvider;
  cookvault: CookVaultClient;
  version: string;
}

interface HealthReport {
  ok: boolean;
  provider: string;
  model: string;
  version: string;
  detail?: string;
  cookvault: { ok: boolean; detail?: string };
}

export function createApp(deps: AppDeps) {
  // A health check that pinged the model on every call would be a way to
  // make the model slower; the answer is cached briefly instead.
  let cached: { at: number; report: HealthReport } | undefined;
  const HEALTH_TTL_MS = 10_000;

  async function health(): Promise<HealthReport> {
    if (cached && Date.now() - cached.at < HEALTH_TTL_MS) return cached.report;
    const [model, cookvault] = await Promise.all([deps.provider.ping(), deps.cookvault.ping()]);
    const report: HealthReport = {
      ok: model.ok && cookvault.ok,
      provider: deps.provider.name,
      model: deps.provider.model,
      version: deps.version,
      ...(model.detail ? { detail: model.detail } : cookvault.detail ? { detail: cookvault.detail } : {}),
      cookvault,
    };
    cached = { at: Date.now(), report };
    return report;
  }

  async function chat(request: Request): Promise<Response> {
    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return Response.json({ detail: "Body must be JSON" }, { status: 400 });
    }
    const parsed = chatBodySchema.safeParse(body);
    if (!parsed.success) {
      return Response.json({ detail: parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ") }, { status: 400 });
    }
    const last = parsed.data.messages[parsed.data.messages.length - 1];
    if (!last || last.role !== "user" || !last.content.trim()) {
      return Response.json({ detail: "The last message must be from the user and not empty" }, { status: 400 });
    }

    const report = await health();
    if (!report.ok) {
      return Response.json({ detail: `ChefNexus is unavailable: ${report.detail ?? "model or CookVault unreachable"}` }, { status: 503 });
    }

    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        let closed = false;
        const emit = (event: Parameters<typeof encodeSse>[0]) => {
          if (closed) return;
          try {
            controller.enqueue(encoder.encode(encodeSse(event)));
          } catch {
            closed = true;
          }
        };
        deps.agent
          .run({ conversationId: parsed.data.conversation_id, messages: parsed.data.messages, signal: request.signal }, emit)
          .catch((err) => {
            log("error", "api", "unhandled turn failure", { error: String(err) });
            emit({ event: "error", data: { message: "ChefNexus hit a problem answering that." } });
          })
          .finally(() => {
            closed = true;
            try {
              controller.close();
            } catch {
              /* already closed by the client */
            }
          });
      },
    });
    return new Response(stream, { headers: SSE_HEADERS });
  }

  return {
    async fetch(request: Request): Promise<Response> {
      const url = new URL(request.url);
      const started = Date.now();
      let response: Response;
      if (request.method === "GET" && url.pathname === "/health") {
        const report = await health();
        response = Response.json(report, { status: report.ok ? 200 : 503 });
      } else if (request.method === "POST" && url.pathname === "/chat") {
        response = await chat(request);
      } else {
        response = Response.json({ detail: "Not found" }, { status: 404 });
      }
      log("info", "api", "request", { method: request.method, path: url.pathname, status: response.status, ms: Date.now() - started });
      return response;
    },
  };
}
