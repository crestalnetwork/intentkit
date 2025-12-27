import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable static export for production build
  // We only enable this in production because 'rewrites' (used in dev) are incompatible with 'export'
  output: process.env.NODE_ENV === "development" ? undefined : "export",

  // Disable image optimization for static export compatibility
  images: {
    unoptimized: true,
  },

  // Proxy API requests to FastAPI backend during development
  // Note: You can bypass this proxy by setting NEXT_PUBLIC_API_BASE_URL
  // in .env.local to directly access the backend (e.g., "http://localhost:8000")
  async rewrites() {
    // Rewrites are not supported in static export, so we only return them in development
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
