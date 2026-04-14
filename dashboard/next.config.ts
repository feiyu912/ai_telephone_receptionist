import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for Docker deployment — produces a minimal standalone server bundle
  // at .next/standalone that the Dockerfile copies into the runtime image.
  output: "standalone",
};

export default nextConfig;
