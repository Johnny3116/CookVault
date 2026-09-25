import { z } from "zod";

/** Everything the service needs, read once at boot and refused loudly if
 *  wrong. No default for the agent key: a surface that can write should
 *  never come up on a value nobody chose. */
const schema = z.object({
  PORT: z.coerce.number().int().positive().default(8500),

  // The model. `ollama` is the only provider today; the abstraction in
  // provider/ is what keeps the rest of the code from caring.
  AI_PROVIDER: z.enum(["ollama"]).default("ollama"),
  AI_BASE_URL: z.string().url().default("http://127.0.0.1:11435"),
  AI_MODEL: z.string().min(1).default("qwen3:8b"),
  // Always sent explicitly: Ollama's own default truncates silently, and a
  // truncated prompt comes back as a model that looks stupid, not as an error.
  AI_NUM_CTX: z.coerce.number().int().positive().default(8192),
  AI_TEMPERATURE: z.coerce.number().min(0).max(2).default(0.2),
  // Qwen3 reasons before answering when allowed to. Off by default: the GPU
  // is shared with the voice stack and tool selection has proven fine
  // without it. Flip on to trade seconds for judgement.
  AI_THINK: z
    .string()
    .default("false")
    .transform((v) => v === "true" || v === "1"),
  AI_TIMEOUT_MS: z.coerce.number().int().positive().default(180_000),

  // CookVault's /agent surface and the key that opens it.
  COOKVAULT_ORIGIN: z.string().url().default("http://backend:8000"),
  AGENT_API_KEY: z.string().min(32, "AGENT_API_KEY must be at least 32 characters (CookVault refuses shorter ones too)"),

  // The loop's bounds. A model that keeps calling tools is not making progress.
  MAX_TOOL_ROUNDS: z.coerce.number().int().positive().max(20).default(6),
  // How much of the conversation the model sees. Older turns are dropped,
  // never summarised: a summary is a place for a model to invent a recipe.
  CONTEXT_MESSAGES: z.coerce.number().int().positive().default(24),

  AUDIT_LOG_PATH: z.string().default("./data/audit.jsonl"),
  LOG_LEVEL: z.enum(["debug", "info", "warn", "error"]).default("info"),
});

export type Config = z.infer<typeof schema>;

export function loadConfig(env: Record<string, string | undefined> = process.env): Config {
  const result = schema.safeParse(env);
  if (!result.success) {
    const problems = result.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("\n  ");
    throw new Error(`cookvault-assistant configuration is invalid:\n  ${problems}`);
  }
  return result.data;
}
