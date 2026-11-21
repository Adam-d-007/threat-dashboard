/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The method page imports ../docs/SCORING.md from outside web/.
  server: { fs: { allow: [".."] } },
  // Two pages: the site, and the small badge other sites embed in a frame.
  build: { rollupOptions: { input: { main: "index.html", badge: "badge.html" } } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
