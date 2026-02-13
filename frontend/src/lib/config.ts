/**
 * Frontend configuration module
 *
 * Centralizes environment variables and configuration settings.
 * All configurable values should be accessed through this module.
 */

/**
 * Application configuration object
 *
 * Environment variables prefixed with NEXT_PUBLIC_ are exposed to the browser.
 * See .env.example for available configuration options.
 */
export const config = {
  /**
   * API Base URL for backend requests
   *
   * - In development with proxy: "/api" (default)
   * - In development without proxy: "http://localhost:8000"
   * - In production: Should be set to the actual backend URL or left as "/api"
   *   if served from the same domain
   */
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || "/api",

  /**
   * AWS S3 CDN URL for resolving relative image paths stored in the database.
   *
   * Images are stored as relative paths in the database. This URL is used
   * as a prefix to construct full, accessible image URLs on the frontend.
   *
   * Example: "https://cdn.example.com"
   */
  awsS3CdnUrl: process.env.NEXT_PUBLIC_AWS_S3_CDN_URL || "",
} as const;

/**
 * Type for the config object
 */
export type Config = typeof config;
