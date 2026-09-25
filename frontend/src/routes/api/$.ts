import { createFileRoute } from "@tanstack/react-router";

/**
 * Same-origin proxy for everything under /api.
 *
 * The browser only ever talks to this app's own origin, which means no CORS
 * config, no backend address in the client bundle, one port to expose over
 * Tailscale, and a session cookie the browser actually sends.
 *
 * Two upstreams:
 *
 * - `/api/assistant/*` goes to the Sage service. Before forwarding, the
 *   request's cookie is checked against the backend's `/auth/session`, so the
 *   assistant sits behind John's password gate without knowing the signing
 *   key -- and the assistant itself never needs a port on the host.
 * - everything else goes to the backend as-is.
 *
 * Both origins are read per request from the environment, so a deployment can
 * repoint them without a rebuild.
 */

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
  // fetch decodes the body for us, so passing these on would describe it wrongly.
  "content-encoding",
  "content-length",
]);

const ASSISTANT_PREFIX = "assistant/";

function backendOrigin(): string {
  return process.env["BACKEND_ORIGIN"] ?? "http://backend:8000";
}

function assistantOrigin(): string {
  return process.env["ASSISTANT_ORIGIN"] ?? "http://assistant:8500";
}

function forwardHeaders(request: Request): Headers {
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) headers.set(key, value);
  });
  return headers;
}

async function sessionIsValid(request: Request): Promise<boolean> {
  try {
    const check = await fetch(`${backendOrigin()}/auth/session`, {
      headers: { cookie: request.headers.get("cookie") ?? "" },
      cache: "no-store",
    });
    return check.ok;
  } catch {
    return false;
  }
}

async function proxy({ request, params }: { request: Request; params: { _splat?: string } }) {
  const splat = params._splat ?? "";
  const toAssistant = splat.startsWith(ASSISTANT_PREFIX);

  if (toAssistant && !(await sessionIsValid(request))) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const path = toAssistant ? splat.slice(ASSISTANT_PREFIX.length) : splat;
  const target = new URL(`${toAssistant ? assistantOrigin() : backendOrigin()}/${path}`);
  target.search = new URL(request.url).search;

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers: forwardHeaders(request),
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: "manual",
      signal: request.signal,
    });
  } catch (err) {
    if (request.signal.aborted) return new Response(null, { status: 499 });
    console.error(`Proxy to ${target.pathname} failed:`, err);
    return Response.json(
      { detail: toAssistant ? "Sage is unreachable" : "Backend unreachable" },
      { status: 502 },
    );
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    const name = key.toLowerCase();
    if (!HOP_BY_HOP.has(name) && name !== "set-cookie") responseHeaders.set(key, value);
  });
  // Set-Cookie can legitimately repeat, and collapsing it would break login.
  for (const cookie of upstream.headers.getSetCookie()) {
    responseHeaders.append("set-cookie", cookie);
  }

  // The body is streamed through untouched, which is what lets the assistant's
  // server-sent events reach the browser as they are produced.
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export const Route = createFileRoute("/api/$")({
  server: {
    handlers: {
      GET: proxy,
      POST: proxy,
      PUT: proxy,
      PATCH: proxy,
      DELETE: proxy,
      HEAD: proxy,
      OPTIONS: proxy,
    },
  },
});
