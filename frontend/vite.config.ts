import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import tailwindcss from "@tailwindcss/vite";
import viteReact from "@vitejs/plugin-react";
import { nitro } from "nitro/vite";
import { defineConfig } from "vite";
import tsConfigPaths from "vite-tsconfig-paths";

// Plain TanStack Start, no Lovable wrapper. The order matters: Start's plugin
// must come before React's, and nitro is what turns the build into something
// a server can run. The `bun` preset produces .output/server/index.mjs, which
// the Dockerfile and `bun run start` both point at.
export default defineConfig({
  plugins: [
    tsConfigPaths({ projects: ["./tsconfig.json"] }),
    tailwindcss(),
    tanstackStart(),
    viteReact(),
    nitro({ preset: "bun" }),
  ],
  server: {
    port: 3420,
  },
});
