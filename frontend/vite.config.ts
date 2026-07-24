import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API base is read from VITE_API_URL at runtime (see src/api.ts), so this
// config stays free of it. Nothing here proxies to the backend on purpose:
// api.py already sends permissive CORS headers, and a proxy would hide a
// connection problem behind a second server that is not there in production.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
