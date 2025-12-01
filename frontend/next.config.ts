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
  async rewrites() {
    // Rewrites are not supported in static export, so we only return them in development
    if (process.env.NODE_ENV !== "development") {
      return [];
    }
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
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
