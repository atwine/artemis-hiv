// Screenshots of the website at the design's 1366 x 768, for checking it side by side with the
// Paper FINAL screens (docs/design/exports/phase5/). Runs only when asked:
//   ARTEMIS_SCREENS=1 npx playwright test screens
import { execFileSync } from "node:child_process";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import type { VisitCheck } from "../src/lib/api/client";

const OUT = path.resolve(__dirname, "..", "..", "docs", "design", "exports", "phase5");

test.skip(!process.env.ARTEMIS_SCREENS, "set ARTEMIS_SCREENS=1 to take the screenshots");

test("the shared frame, before and after the checks", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("main").getByRole("link", { name: "John Doe" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-0-patients.png") });

  await page.getByRole("main").getByRole("link", { name: "John Doe" }).click();
  await expect(page.getByRole("textbox", { name: "Clinical notes" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-S2-before-checks.png") });

  await page.getByRole("region", { name: "Visit steps" }).getByRole("button", { name: "Run checks" }).click();
  await page.screenshot({ path: path.join(OUT, "web-S3-checks-running.png") });
  const results = page.getByRole("region", { name: "Check results" });
  await expect(results).toBeVisible({ timeout: 5 * 60 * 1000 });
  await page.screenshot({ path: path.join(OUT, "web-S4-results.png") });
});

// The AI-review states the design doesn't draw (owner's decision 5). Each is a real reply to a
// rule-checks-only visit check (no model call), with the AI outcome, status and banners the API
// would send for it, computed by e2e/ai_states.py from the backend's own functions.
type AiProblem = "search_unavailable" | "failed" | "unreadable" | "cut_off" | "partly_read";

const STATES: { outcome: AiProblem; patient: string; file: string }[] = [
  { outcome: "search_unavailable", patient: "John Doe", file: "web-S7-search-unavailable.png" },
  { outcome: "failed", patient: "Jane Roe", file: "web-S7-ai-failed.png" },
  { outcome: "cut_off", patient: "John Doe", file: "web-S7-ai-cut-off.png" },
];

async function stubOutcome(page: Page, outcome: AiProblem) {
  await page.route("**/api/patients/*/visits", async (route) => {
    const reply = await route.fetch();
    const body = (await reply.json()) as VisitCheck;
    const severities = JSON.stringify(body.cards.map((c) => c.extension.severity ?? null));
    const states = JSON.parse(
      execFileSync(process.env.PYTHON || "python", [path.join(__dirname, "ai_states.py"), severities], { encoding: "utf8" }),
    );
    const cards =
      outcome === "search_unavailable" // no search, so no guideline references (screen checklist)
        ? body.cards.map((c) => ({ ...c, extension: { ...c.extension, references: [], passages: [] } }))
        : body.cards;
    await route.fulfill({ response: reply, json: { ...body, ...states[outcome], ai_review: outcome, cards } });
  });
}

for (const { outcome, patient, file } of STATES) {
  test(`the AI review ended "${outcome}"`, async ({ page }) => {
    await stubOutcome(page, outcome);
    await page.goto("/");
    await page.getByRole("main").getByRole("link", { name: patient }).click();
    await page.getByRole("region", { name: "Visit steps" }).getByRole("button", { name: "Run checks" }).click();
    const results = page.getByRole("region", { name: "Check results" });
    await expect(results).toBeVisible({ timeout: 5 * 60 * 1000 });
    await results.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(OUT, file) });
  });
}
