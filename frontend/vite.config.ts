import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Development: forward API calls to a running nexus-simulator backend.
  // Set VITE_PROXY_TARGET in .env.local (default: local backend on :8000).
  const target = env.VITE_PROXY_TARGET || "http://localhost:8000";
  const proxied = { target, changeOrigin: true, secure: true };

  return {
    server: {
      host: "::",
      port: 5390,
      // "^/api/" (not "/api") so the /apis page is not sent to the backend.
      proxy: {
        "^/api/": proxied, "^/health$": proxied, "^/readiness$": proxied,
        // Vendor-style API roots used by the API test bench.
        "^/services/": proxied, "^/fscmRestApi/": proxied, "^/sap/": proxied,
      },
    },
    plugins: [react()],
    resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  };
});
