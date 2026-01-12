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
} as const;

/**
 * Type for the config object
 */
export type Config = typeof config;
