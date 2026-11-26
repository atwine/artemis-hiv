// Screenshots of the website at the design's 1366 x 768, for checking it side by side with the
// Paper FINAL screens (docs/design/exports/phase5/). Runs only when asked:
//   ARTEMIS_SCREENS=1 npx playwright test screens
import path from "node:path";

import { expect, test } from "@playwright/test";

import { stubDesignDay, stubOutcome, type AiOutcome } from "./stubs";

const OUT = path.resolve(__dirname, "..", "..", "docs", "design", "exports", "phase5");

test.skip(!process.env.ARTEMIS_SCREENS, "set ARTEMIS_SCREENS=1 to take the screenshots");

test("the shared frame, before and after the checks", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("region", { name: "Waiting" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-S1-board-fresh.png") });

  // Rose (P005), the design's own patient: her labs are typed-in text only.
  await page.goto("/patients/P005");
  await expect(page.getByRole("textbox", { name: "Clinical notes" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-S2-P005.png") });
  await page.goto("/patients/P001");
  await expect(page.getByRole("textbox", { name: "Clinical notes" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-S2-before-checks.png") });

  await page.getByRole("region", { name: "Visit steps" }).getByRole("button", { name: "Run checks" }).click();
  await page.screenshot({ path: path.join(OUT, "web-S3-checks-running.png") });
  const results = page.getByRole("region", { name: "Check results" });
  await expect(results).toBeVisible({ timeout: 5 * 60 * 1000 });
  await page.screenshot({ path: path.join(OUT, "web-S4-results.png") });

  const tray = page.getByRole("region", { name: "Visit steps" });
  await tray.getByRole("button", { name: "Review alert 1" }).click();
  await expect(page.getByRole("region", { name: "Alert 1" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-S4c-alert.png") });
  await tray.getByRole("button", { name: "Override" }).click();
  await expect(page.getByRole("list", { name: "Override reasons" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-S4d-override.png") });
  await page.getByRole("button", { name: /Other \(say why\)/ }).click();
  await page.screenshot({ path: path.join(OUT, "web-S4d-override-other.png") });
});

// The AI-review states the design doesn't draw (owner's decision 5); see e2e/stubs.ts.
const STATES: { outcome: AiOutcome; patient: string; file: string }[] = [
  { outcome: "search_unavailable", patient: "P001", file: "web-S7-search-unavailable.png" },
  { outcome: "failed", patient: "P002", file: "web-S7-ai-failed.png" },
  { outcome: "unreadable", patient: "P002", file: "web-S7-ai-unreadable.png" },
  { outcome: "cut_off", patient: "P001", file: "web-S7-ai-cut-off.png" },
  { outcome: "partly_read", patient: "P001", file: "web-S7-ai-partly-read.png" },
  // GREEN (S7b): no alerts, and the AI review finished cleanly.
  { outcome: "ok", patient: "P002", file: "web-S7b-green.png" },
];

for (const { outcome, patient, file } of STATES) {
  test(`the AI review ended "${outcome}"`, async ({ page }) => {
    await stubOutcome(page, outcome);
    await page.goto(`/patients/${patient}`);
    await page.getByRole("region", { name: "Visit steps" }).getByRole("button", { name: "Run checks" }).click();
    const results = page.getByRole("region", { name: "Check results" });
    await expect(results).toBeVisible({ timeout: 5 * 60 * 1000 });
    await results.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(OUT, file) });
  });
}

// Checks running with the AI review ticked (S3). The request is held and then cancelled, so no
// model is called; the screenshot shows the screen 6 seconds in.
test("checks running, with the AI review", async ({ page }) => {
  await page.route("**/api/patients/*/visits", async (route) => {
    if (route.request().method() !== "POST") return route.continue(); // only the check, not past checks
    await new Promise((r) => setTimeout(r, 9000));
    await route.abort();
  });
  await page.goto("/patients/P001");
  await page.getByRole("checkbox", { name: "AI review" }).check();
  await page.getByRole("region", { name: "Visit steps" }).getByRole("button", { name: "Run checks" }).click();
  await expect(page.getByRole("region", { name: "Checks running" })).toContainText("6 s of about 15 s", { timeout: 10_000 });
  await page.screenshot({ path: path.join(OUT, "web-S3-checks-running-ai.png") });
});

// GREEN with the AI review off (S7b's other banner): a real reply, nothing stubbed.
test("a quiet visit with the AI review off", async ({ page }) => {
  await page.goto("/patients/P002");
  await page.getByRole("region", { name: "Visit steps" }).getByRole("button", { name: "Run checks" }).click();
  await expect(page.getByRole("list", { name: "What was checked" })).toBeVisible({ timeout: 5 * 60 * 1000 });
  await page.screenshot({ path: path.join(OUT, "web-S7b-green-ai-off.png") });
});

// The clinic day as the design draws it (S1, S1b): the real day from the API, with the design's
// states laid over it (e2e/stubs.ts). Only the screenshot sees this; the browser test checks the real states (e2e/board.spec.ts).
test("the clinic day, in the design's states", async ({ page }) => {
  await stubDesignDay(page);
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Continue review" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-S1-board.png") });
  await page.goto("/?view=list");
  await expect(page.getByRole("list", { name: "Today's visits" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-S1b-list.png") });
});

// Finalize (S6a), its confirm step (owner's decision 6) and the saved record (S6b), with John Doe.
test("finalize, the confirm and the record", async ({ page }) => {
  await page.goto("/patients/P001");
  const tray = page.getByRole("region", { name: "Visit steps" });
  await tray.getByRole("button", { name: "Run checks" }).click();
  await expect(page.getByRole("region", { name: "Check results" })).toBeVisible({ timeout: 5 * 60 * 1000 });
  await tray.getByRole("button", { name: /^Finalize, / }).click();
  await expect(page.getByRole("region", { name: "Finalize" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-S6a-finalize-locked.png") });
  await page.getByRole("button", { name: /^Review alert 1/ }).click();
  await tray.getByRole("button", { name: "Accept alert" }).click();
  await tray.getByRole("button", { name: "Finalize visit" }).click();
  await expect(tray).toContainText("Decisions can't be changed after this.");
  await page.screenshot({ path: path.join(OUT, "web-S6-confirm.png") });
  await tray.getByRole("button", { name: "Finalize", exact: true }).click();
  await expect(page.getByRole("region", { name: "Visit record" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-S6b-record.png") });

  // His next visit, before the checks: the finalized one is listed under Past checks.
  await page.goto("/patients/P001");
  await expect(page.getByRole("list", { name: "Past checks" })).toContainText("Finalized");
  await page.screenshot({ path: path.join(OUT, "web-S2-past-checks.png") });
});
