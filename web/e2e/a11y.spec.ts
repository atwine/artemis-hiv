// Accessibility audit: every built screen, checked with axe-core against WCAG 2.2 AA. A screen
// passes when axe finds no WCAG problem on it. Automated checks catch only part of what matters
// (keyboard use and screen-reader wording still need a person), so this is a floor, not a seal.
// Set ARTEMIS_A11Y_REPORT=<folder> to also write each screen's full axe result there.
import fs from "node:fs";
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { E2E } from "./ports";
import { stubDesignDay, stubOutcome, type AiOutcome } from "./stubs";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const CHECK_WAIT = { timeout: 5 * 60 * 1000 };

// Owner's decision (2026-11-27, docs/decisions.tsv): the tray's not-yet-reached step names keep the
// design's grey (#7e8796 on the dark tray, 4.4:1, under AA's 4.5). Only their contrast check is
// skipped; every other rule still runs on them.
const KEPT_DESIGN_GREY = ".text-tray-todo";

/** Runs axe on the page as it is now and records any WCAG problem under the screen's name. */
async function audit(page: Page, screen: string) {
  const result = await new AxeBuilder({ page }).withTags([...WCAG, "best-practice"]).analyze();
  const report = process.env.ARTEMIS_A11Y_REPORT;
  if (report) {
    fs.mkdirSync(report, { recursive: true });
    fs.writeFileSync(path.join(report, `${screen}.json`), JSON.stringify(result.violations, null, 2));
  }
  const wcag = [];
  for (const v of result.violations.filter((v) => v.tags.some((t) => WCAG.includes(t)))) {
    const where = [];
    for (const n of v.nodes) {
      const selector = n.target.join(" ");
      const kept =
        v.id === "color-contrast" &&
        (await page.locator(selector).evaluate((el, kept) => el.closest(kept) !== null, KEPT_DESIGN_GREY));
      if (!kept) where.push(selector);
    }
    if (where.length) wcag.push({ rule: v.id, impact: v.impact, help: v.help, where });
  }
  expect.soft(wcag, `WCAG problems on "${screen}"`).toEqual([]);
}

const tray = (page: Page) => page.getByRole("region", { name: "Visit steps" });

async function runChecks(page: Page) {
  await tray(page).getByRole("button", { name: "Run checks" }).click();
  await expect(page.getByRole("region", { name: "Check results" })).toBeVisible(CHECK_WAIT);
}

test("the clinic day: board and list", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("region", { name: "Waiting" })).toBeVisible();
  await audit(page, "board-fresh");

  await stubDesignDay(page); // finalized cards, one needing review, one AI review failed
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Continue review" })).toBeVisible();
  await audit(page, "board");
  await page.goto("/?view=list");
  await expect(page.getByRole("list", { name: "Today's visits" })).toBeVisible();
  await audit(page, "list");
});

test("adding a case: both parts, with a problem shown, and the day links it makes", async ({ page }) => {
  const steps = page.getByRole("region", { name: "New case steps" });
  await page.goto("/cases/new");
  await page.getByRole("button", { name: "Add previous ART, with dates" }).click();
  await page.getByRole("group", { name: "Previous ART 1 drugs" }).getByRole("button", { name: "AZT", exact: true }).click();
  await steps.getByRole("button", { name: "Next: labs and clinical notes" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toBeVisible();
  await audit(page, "add-case-part1");

  await page.getByLabel("ID", { exact: true }).fill("P192");
  await page.getByLabel("Time", { exact: true }).fill("10:00");
  await page.getByLabel("Previous ART 1 from", { exact: true }).fill("2016-03-01");
  await page.getByLabel("Previous ART 1 to", { exact: true }).fill("2019-08-15");
  await steps.getByRole("button", { name: "Next: labs and clinical notes" }).click();
  await page.getByLabel("Result 1 test").selectOption("creatinine");
  await page.getByRole("button", { name: "Add result" }).click();
  await expect(page.getByLabel("Complaints", { exact: true })).toBeVisible();
  await audit(page, "add-case-part2");

  // A case on a later day gives the board a link to it.
  const added = await page.request.post(`${E2E.apiUrl}/api/patients`, {
    data: { patient_id: "P193", visit_date: "2099-07-07", appointment_time: "09:00" },
  });
  expect(added.ok()).toBe(true);
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "Other clinic days" })).toBeVisible();
  await audit(page, "board-day-links");
});

test("a visit: notes, checks running, results, alert, override, finalize and the record", async ({ page }) => {
  await page.goto("/patients/P001");
  await expect(page.getByRole("textbox", { name: "Clinical notes" })).toBeVisible();
  await audit(page, "visit-notes");

  // Hold the check so the running screen stays up while it is audited; then let it through.
  let release = () => {};
  const held = new Promise<void>((r) => (release = r));
  await page.route("**/api/patients/*/visits", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await held;
    await route.continue();
  });
  await page.getByRole("checkbox", { name: "AI review" }).check();
  await page.getByRole("checkbox", { name: "AI review" }).uncheck(); // no model call
  await tray(page).getByRole("button", { name: "Run checks" }).click();
  await expect(page.getByRole("region", { name: "Checks running" })).toBeVisible();
  await audit(page, "checks-running");
  release();
  await expect(page.getByRole("region", { name: "Check results" })).toBeVisible(CHECK_WAIT);
  await audit(page, "results");

  await tray(page).getByRole("button", { name: "Review alert 1" }).click();
  await expect(page.getByRole("region", { name: "Alert 1" })).toBeVisible();
  await audit(page, "alert");
  await tray(page).getByRole("button", { name: "Override" }).click();
  await expect(page.getByRole("list", { name: "Override reasons" })).toBeVisible();
  await audit(page, "override");
  await page.getByRole("button", { name: /Other \(say why\)/ }).click();
  await audit(page, "override-other");
  await tray(page).getByRole("button", { name: "Back to the alert" }).click();

  await tray(page).getByRole("button", { name: /^Finalize, / }).click();
  await expect(page.getByRole("region", { name: "Finalize" })).toBeVisible();
  await audit(page, "finalize-locked");
  await page.getByRole("button", { name: /^Review alert 1/ }).click();
  await tray(page).getByRole("button", { name: "Accept alert" }).click();
  await tray(page).getByRole("button", { name: "Finalize visit" }).click();
  await expect(tray(page)).toContainText("Decisions can't be changed after this.");
  await audit(page, "finalize-confirm");
  await tray(page).getByRole("button", { name: "Finalize", exact: true }).click();
  await expect(page.getByRole("region", { name: "Visit record" })).toBeVisible();
  await audit(page, "record");

  await page.goto("/patients/P001");
  await expect(page.getByRole("list", { name: "Past checks" })).toContainText("Finalized");
  await audit(page, "past-checks");
});

test("a quiet visit with the AI review off (GREEN)", async ({ page }) => {
  await page.goto("/patients/P002");
  await tray(page).getByRole("button", { name: "Run checks" }).click();
  await expect(page.getByRole("list", { name: "What was checked" })).toBeVisible(CHECK_WAIT);
  await audit(page, "green-ai-off");
});

test("too many checks: the error message", async ({ page }) => {
  await page.route("**/api/patients/*/visits", async (route) =>
    route.request().method() === "POST"
      ? route.fulfill({ status: 429, json: { detail: "Too many visit checks: wait a moment and try again." } })
      : route.continue(),
  );
  await page.goto("/patients/P001");
  await tray(page).getByRole("button", { name: "Run checks" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toBeVisible();
  await audit(page, "error-too-many");
});

const OUTCOMES: { outcome: AiOutcome; patient: string }[] = [
  { outcome: "search_unavailable", patient: "P001" },
  { outcome: "failed", patient: "P002" },
  { outcome: "unreadable", patient: "P002" },
  { outcome: "cut_off", patient: "P001" },
  { outcome: "partly_read", patient: "P001" },
  { outcome: "ok", patient: "P002" }, // GREEN with the AI review on
];

for (const { outcome, patient } of OUTCOMES) {
  test(`the AI review ended "${outcome}"`, async ({ page }) => {
    await stubOutcome(page, outcome);
    await page.goto(`/patients/${patient}`);
    await runChecks(page);
    await audit(page, `ai-${outcome}`);
  });
}
