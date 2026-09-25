import { log } from "./log.ts";

/** CookVault's /agent surface, as a client.
 *
 * Everything Sage knows about the cookbook comes through here, and everything
 * it proposes goes out through here. The surface is CookVault's, the key
 * opens exactly that surface, and CookVault validates every write -- which is
 * why this file has no business logic in it.
 */
export class CookVaultError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail);
    this.name = "CookVaultError";
  }
}

export interface CookVaultClient {
  get<T>(path: string, query?: Record<string, string | number | undefined>): Promise<T>;
  post<T>(path: string, body: unknown): Promise<T>;
  /** Is the backend up and the agent surface switched on? */
  ping(): Promise<{ ok: boolean; detail?: string }>;
}

export function createCookVaultClient(origin: string, apiKey: string): CookVaultClient {
  const base = origin.replace(/\/$/, "");

  async function call<T>(method: string, path: string, body?: unknown, query?: Record<string, string | number | undefined>): Promise<T> {
    const url = new URL(`${base}${path}`);
    for (const [key, value] of Object.entries(query ?? {})) {
      if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
    }
    const started = Date.now();
    let res: Response;
    try {
      res = await fetch(url, {
        method,
        headers: { "content-type": "application/json", "x-api-key": apiKey },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(30_000),
      });
    } catch (err) {
      throw new CookVaultError(0, `CookVault unreachable: ${err instanceof Error ? err.message : String(err)}`);
    }
    log("debug", "tool", "cookvault call", { method, path, status: res.status, ms: Date.now() - started });
    if (!res.ok) {
      let detail = `CookVault answered ${res.status}`;
      try {
        const parsed = (await res.json()) as { detail?: unknown };
        if (typeof parsed.detail === "string") detail = parsed.detail;
        else if (parsed.detail !== undefined) detail = JSON.stringify(parsed.detail);
      } catch {
        /* keep the status line */
      }
      throw new CookVaultError(res.status, detail);
    }
    return (await res.json()) as T;
  }

  return {
    get: (path, query) => call("GET", path, undefined, query),
    post: (path, body) => call("POST", path, body),
    async ping() {
      try {
        await call("GET", "/agent/manifest");
        return { ok: true };
      } catch (err) {
        if (err instanceof CookVaultError) {
          if (err.status === 503) return { ok: false, detail: "CookVault's agent surface is switched off (AGENT_API_KEY unset there)" };
          if (err.status === 401) return { ok: false, detail: "CookVault rejected the agent key" };
          return { ok: false, detail: err.detail };
        }
        return { ok: false, detail: String(err) };
      }
    },
  };
}
