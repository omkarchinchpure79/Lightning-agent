import { defineConfig, devices } from "@playwright/test";

// C4 (roadmap): one smoke test protecting the flows B2/C1/C2 all touch —
// signup -> login -> create student -> results renders 3 bands -> shortlist
// persists. Starts BOTH the API (uvicorn) and the Next.js dev server so the
// test drives the real stack, not a mock.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: "python -m uvicorn api.main:app --port 8000",
      cwd: "..",
      url: "http://localhost:8000/api/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      // Dev server (Turbopack) compiles pages on-demand and spawns a build-worker
      // per route on first hit — under this harness that fanned out to 40+ node
      // processes and never converged within any reasonable timeout. A prod build
      // compiles once upfront and starts instantly, which is what a smoke test
      // needs anyway (it's checking the app works, not iterating on it).
      command: "npm run build && npm run start",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 300_000,
    },
  ],
});
