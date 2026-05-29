/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In dev the SPA calls relative /api/*, proxied to the Hono BFF (P1b).
export default defineConfig({
  // Static demo (VITE_STATIC) ships under https://<user>.github.io/<repo>/ — relative asset
  // URLs work there without baking in the repo name (and still work on a custom root domain).
  base: process.env.VITE_STATIC ? "./" : "/",
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8787", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
