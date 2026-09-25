/** Structured lines to stdout. One JSON object per line, so `docker logs`
 *  stays greppable and a failure can be traced to the layer it came from:
 *  every entry names one of ui, api, orchestrator, model, tool. */

export type LogLevel = "debug" | "info" | "warn" | "error";
export type Layer = "api" | "orchestrator" | "model" | "tool" | "audit";

const ORDER: Record<LogLevel, number> = { debug: 10, info: 20, warn: 30, error: 40 };

let threshold: LogLevel = "info";

export function setLogLevel(level: LogLevel) {
  threshold = level;
}

export function log(level: LogLevel, layer: Layer, message: string, fields: Record<string, unknown> = {}) {
  if (ORDER[level] < ORDER[threshold]) return;
  const line = JSON.stringify({ ts: new Date().toISOString(), level, layer, message, ...fields });
  if (level === "error" || level === "warn") console.error(line);
  else console.log(line);
}
