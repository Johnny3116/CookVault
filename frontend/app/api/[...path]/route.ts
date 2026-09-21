import { NextRequest } from "next/server";

/**
 * Same-origin proxy to the backend API.
 *
 * The browser only ever talks to this app's own origin, which means no CORS
 * config, no backend address in the client bundle, one port to expose over
 * Tailscale, and a session cookie the browser actually sends.
 *
 * This is a route handler rather than a `rewrites()` entry on purpose:
 * Next resolves rewrite destinations at BUILD time and bakes them into the
 * routes manifest, so a rewrite could not be repointed by an environment
 * variable at deploy time. This reads BACKEND_ORIGIN per request.
 */

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Headers that describe a specific hop and must not be forwarded verbatim.
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

function backendOrigin(): string {
  return process.env.BACKEND_ORIGIN ?? "http://backend:8000";
}

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const target = new URL(`${backendOrigin()}/${path.join("/")}`);
  target.search = req.nextUrl.search;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) headers.set(key, value);
  });

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      redirect: "manual",
      cache: "no-store",
    });
  } catch (err) {
    console.error(`Proxy to ${target.pathname} failed:`, err);
    return Response.json({ detail: "Backend unreachable" }, { status: 502 });
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase()) && key.toLowerCase() !== "set-cookie") {
      responseHeaders.set(key, value);
    }
  });
  // Set-Cookie can legitimately repeat, and collapsing it would break login.
  for (const cookie of upstream.headers.getSetCookie()) {
    responseHeaders.append("set-cookie", cookie);
  }

  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const HEAD = proxy;
export const OPTIONS = proxy;
