import { defineConfig, defineWorker } from "cf/config";

/**
 * ContextPulse offline demo on Cloudflare (static files only, no Python backend).
 *
 * `npm run deploy` uploads ../../static as an assets-only Worker. There is no /api here,
 * so /api/bootstrap answers 404 and app.js switches to its offline demo mode
 * (browser-side logic, template text instead of AI).
 *
 * When the FastAPI backend runs on a VPS, point contextpulse.nexusweb.az at the VPS
 * instead (FastAPI serves the same static files and the real /api), and remove the
 * domain from this Worker. See README.md in this folder.
 */
export default defineConfig({
  worker: defineWorker({
    name: "contextpulse-demo",
    compatibilityDate: "2026-11-23",
    // No public *.workers.dev address: served only on its own subdomain.
    workersDev: false,
    previewUrls: false,
    domains: ["contextpulse.nexusweb.az"],
    assets: {
      htmlHandling: "auto-trailing-slash",
      // Unknown paths (including /api/*) return 404 so the app detects "no backend".
      notFoundHandling: "none",
    },
  }),
});
