import type { NextConfig } from "next";

// Where the FastAPI server lives. Read at build time and on the server only: the
// browser calls /api/* on this app and Next.js forwards it, so no CORS is needed.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    // Rewrites time out after 30 s by default. The first request for a model downloads
    // and loads it, which can take minutes, so allow up to 10 minutes.
    proxyTimeout: 10 * 60_000,
  },
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
