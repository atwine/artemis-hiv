// Screenshots of the website at the design's 1366 x 768, for checking it side by side with the
// Paper FINAL screens (docs/design/exports/phase5/). Runs only when asked:
//   ARTEMIS_SCREENS=1 npx playwright test screens
import path from "node:path";

import { expect, test } from "@playwright/test";

import { runRuleChecks } from "./checks";

import { DESIGN_PLAN, standIn, stubDesignDay, stubOutcome, type AiOutcome } from "./stubs";

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

  await runRuleChecks(page);
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
    await runRuleChecks(page);
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
  await runRuleChecks(page);
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

// The note changed after the checks ran (owner, 2026-11-27: "A, a banner"), on John Doe's results.
test("the note changed after the checks", async ({ page }) => {
  await page.goto("/patients/P001");
  await runRuleChecks(page);
  const tray = page.getByRole("region", { name: "Visit steps" });
  await expect(page.getByRole("region", { name: "Check results" })).toBeVisible({ timeout: 5 * 60 * 1000 });
  await tray.getByRole("button", { name: "Clinical notes, done" }).click();
  await page.getByRole("textbox", { name: "Clinical notes" }).fill("Routine follow-up. No complaints. Stop ibuprofen.");
  await tray.getByRole("button", { name: "Checks, done" }).click();
  await expect(page.getByRole("status").filter({ hasText: "The note changed after these checks ran." })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-S4-note-changed.png") });
});

// Compare plans (S5) with the design's own plan as a stand-in reply (no model is called), on Jane
// Roe's visit (no alerts); then the same screen scrolled to the monitoring and counselling lists.
test("compare plans", async ({ page }) => {
  await page.goto("/patients/P002");
  await runRuleChecks(page);
  await expect(page.getByRole("region", { name: "Check results" })).toBeVisible({ timeout: 5 * 60 * 1000 });
  await standIn(page, { json: DESIGN_PLAN });
  await page.getByRole("region", { name: "Visit steps" }).getByRole("button", { name: "Compare plans" }).click();
  await expect(page.getByRole("list", { name: "Counselling" })).toBeAttached();
  await page.screenshot({ path: path.join(OUT, "web-S5-plan.png") });
  await page.getByRole("list", { name: "Counselling" }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(OUT, "web-S5-plan-lists.png") });
});

// Adding a case (S8a, S8b), filled in as the design draws Grace Atim; not saved.
test("adding a case, both parts", async ({ page }) => {
  await page.goto("/cases/new");
  await page.getByLabel("ID", { exact: true }).fill("P010");
  await page.getByLabel("Name", { exact: true }).fill("Grace Atim");
  await page.getByLabel("Age", { exact: true }).fill("41");
  await page.getByLabel("Sex", { exact: true }).selectOption({ label: "Female" });
  await page.getByLabel("Time", { exact: true }).fill("11:00");
  await page.getByLabel("Visit type", { exact: true }).selectOption("Routine review");
  await page.getByRole("button", { name: /^TLD = / }).click();
  await page.getByRole("textbox", { name: "Other medicine", exact: true }).fill("Ibuprofen 400 mg, three times a day");
  await page.getByRole("button", { name: "Add medicine" }).click();
  await page.getByRole("button", { name: "Add previous ART, with dates" }).click();
  const past = page.getByRole("group", { name: "Previous ART 1 drugs" });
  for (const drug of ["AZT", "3TC", "NVP"]) await past.getByRole("button", { name: drug, exact: true }).click();
  await page.getByLabel("Previous ART 1 from", { exact: true }).fill("2016-03-01");
  await page.getByLabel("Previous ART 1 to", { exact: true }).fill("2019-08-15");
  await page.screenshot({ path: path.join(OUT, "web-S8a-add-case.png") });

  await page.getByRole("region", { name: "New case steps" }).getByRole("button", { name: "Next: labs and clinical notes" }).click();
  await page.getByLabel("Result 1 test").selectOption("creatinine");
  await page.getByLabel("Result 1 date").fill("2026-11-27");
  await page.getByLabel("Result 1 value").fill("0.8");
  await page.getByLabel("Complaints", { exact: true }).fill("None today");
  await page.getByLabel("Exam findings", { exact: true }).fill("Unremarkable");
  await page.getByLabel("Clinical notes", { exact: true }).click();
  await page.screenshot({ path: path.join(OUT, "web-S8b-add-case.png") });
});

// Finalize (S6a), its confirm step (owner's decision 6) and the saved record (S6b), with John Doe.
test("finalize, the confirm and the record", async ({ page }) => {
  await page.goto("/patients/P001");
  const tray = page.getByRole("region", { name: "Visit steps" });
  await runRuleChecks(page);
  await expect(page.getByRole("region", { name: "Check results" })).toBeVisible({ timeout: 5 * 60 * 1000 });
  await tray.getByRole("button", { name: /^Finalize, / }).click();
  await expect(page.getByRole("region", { name: "Finalize" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-S6a-finalize-locked.png") });
  await page.getByRole("button", { name: /^Review alert 1/ }).click();
  await tray.getByRole("button", { name: "Accept alert" }).click();
  // Every alert answered: Compare plans is next, so Finalize is reached from the tray's step.
  await tray.getByRole("button", { name: /^Finalize, / }).click();
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
