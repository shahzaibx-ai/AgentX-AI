import type { NextConfig } from "next";

// Where the FastAPI server lives. Server-side only; the browser calls /api/* on
// this app and Next.js forwards it, so there is no CORS setup to manage.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Compression would buffer the chat event stream; let your proxy/CDN compress instead.
  compress: false,
  experimental: {
    // Uploads pass through the /api rewrite, which caps bodies at 10 MB by default.
    // Library files are up to 100 MB and are sent one per request.
    proxyClientMaxBodySize: "110mb",
    // Big uploads and slow first answers need more than the 30 s default.
    proxyTimeout: 120_000,
  },
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
