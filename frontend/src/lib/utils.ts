import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import { config } from "./config";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Resolve an image path to a full URL.
 *
 * - If the value is already an absolute URL (starts with "http"), return it as-is.
 * - Otherwise, prepend the configured AWS S3 CDN base URL.
 * - Returns `null` for falsy inputs so callers can safely use it in
 *   conditional rendering (e.g. `getImageUrl(agent.picture) ?? fallback`).
 */
export function getImageUrl(path: string | null | undefined): string | null {
  if (!path) return null;

  // Already an absolute URL — nothing to do.
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  const cdnBase = config.awsS3CdnUrl;
  if (!cdnBase) {
    // No CDN configured; return the raw path as a best-effort fallback.
    return path;
  }

  // Avoid double slashes when joining.
  const base = cdnBase.endsWith("/") ? cdnBase.slice(0, -1) : cdnBase;
  const rel = path.startsWith("/") ? path.slice(1) : path;
  return `${base}/${rel}`;
}
