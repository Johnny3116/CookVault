import { fileURLToPath } from "node:url";

import { Agent, loadSystemPrompt } from "./agent.ts";
import { createFileAuditLog } from "./audit.ts";
import { loadConfig } from "./config.ts";
import { createCookVaultClient } from "./cookvault.ts";
import { log, setLogLevel } from "./log.ts";
import { OllamaProvider } from "./provider/ollama.ts";
import { createApp } from "./server.ts";
import { defaultRegistry } from "./tools/index.ts";

const VERSION = "0.1.0";

const config = loadConfig();
setLogLevel(config.LOG_LEVEL);

const provider = new OllamaProvider(config);
const cookvault = createCookVaultClient(config.COOKVAULT_ORIGIN, config.AGENT_API_KEY);
const agent = new Agent({
  provider,
  tools: defaultRegistry(),
  audit: createFileAuditLog(config.AUDIT_LOG_PATH),
  toolContext: { cookvault, model: provider.model, version: VERSION },
  // fileURLToPath rather than .pathname: on Windows the latter is "/D:/..."
  // with %20 for spaces, which is not a path anything can open.
  systemPrompt: loadSystemPrompt(fileURLToPath(new URL("../prompts/system.md", import.meta.url))),
  maxToolRounds: config.MAX_TOOL_ROUNDS,
  contextMessages: config.CONTEXT_MESSAGES,
});

const app = createApp({ agent, provider, cookvault, version: VERSION });

Bun.serve({
  port: config.PORT,
  hostname: "0.0.0.0",
  // A model turn can take a while on a shared GPU; do not cut the stream.
  idleTimeout: 255,
  fetch: app.fetch,
});

log("info", "api", "cookvault-assistant listening", {
  port: config.PORT,
  provider: provider.name,
  model: provider.model,
  cookvault: config.COOKVAULT_ORIGIN,
  think: config.AI_THINK,
});

// Say at boot whether the two things this depends on are there. Not fatal:
// the service must stay up while Ollama warms, and /health keeps reporting.
Promise.all([provider.ping(), cookvault.ping()]).then(([model, cv]) => {
  log(model.ok ? "info" : "warn", "model", model.ok ? "model reachable" : "model NOT reachable", { detail: model.detail });
  log(cv.ok ? "info" : "warn", "tool", cv.ok ? "CookVault agent surface reachable" : "CookVault agent surface NOT reachable", { detail: cv.detail });
});
