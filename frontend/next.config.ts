import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // The /api/* proxy to the backend lives in app/api/[...path]/route.ts rather
  // than in `rewrites()` -- see that file for why.
};

export default nextConfig;
