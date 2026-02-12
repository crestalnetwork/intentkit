import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Use Next.js runtime (SSR/Node server) in all environments.
  // This disables static export so dynamic routes like /agent/[id]/tasks can build.
  output: undefined,

  // Keep image optimization enabled for runtime mode
  images: {
    unoptimized: false,
  },

  // Proxy API requests to FastAPI backend during development
  // Note: You can bypass this proxy by setting NEXT_PUBLIC_API_BASE_URL
  // in .env.local to directly access the backend (e.g., "http://localhost:8000")
  async rewrites() {
    if (process.env.NODE_ENV !== "development") {
      return [];
    }
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/:path*",
      },
      {
        source: "/docs",
        destination: "http://127.0.0.1:8000/docs",
      },
      {
        source: "/openapi.json",
        destination: "http://127.0.0.1:8000/openapi.json",
      },
    ];
  },
};

export default nextConfig;
