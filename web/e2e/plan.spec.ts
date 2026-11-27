// Compare plans (Paper FINAL S5): the AI's management plan next to the doctor's, made only when the
// doctor asks for it (owner, 2026-11-26). The browser tests' backend has no model server, so the
// real reply is its refusal; a made, flagged or failed plan is a stand-in reply (no model is called).
import { expect, test, type Page } from "@playwright/test";

import { PLAN, standIn } from "./stubs";

const CHECK_WAIT = { timeout: 5 * 60 * 1000 };
const tray = (page: Page) => page.getByRole("region", { name: "Visit steps" });

/** Jane Roe's visit (P002, no alerts), checked with the rule checks only. */
async function checkedVisit(page: Page) {
  await page.goto("/patients/P002");
  await tray(page).getByRole("button", { name: "Run checks" }).click();
  await expect(page.getByRole("region", { name: "Check results" })).toBeVisible(CHECK_WAIT);
}

test("with every alert answered, Compare plans is next; the backend's refusal is shown as sent", async ({ page }) => {
  await checkedVisit(page);
  await tray(page).getByRole("button", { name: "Compare plans" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    /No AI model server is set up\.|The guideline search is unavailable, so no plan was made\./,
  );
  // Finalize stays one step away.
  await tray(page).getByRole("button", { name: "Go to finalize" }).click();
  await expect(tray(page).getByRole("button", { name: "Finalize visit" })).toBeVisible();
});

test("a made plan: the regimen, each problem with the AI's note about your plan, then monitoring and counselling", async ({ page }) => {
  await checkedVisit(page);
  const calls = await standIn(page, { json: PLAN });
  await tray(page).getByRole("button", { name: "Compare plans" }).click();

  const plan = page.getByRole("region", { name: "AI plan vs your plan" });
  await expect(plan).toContainText("Switch");
  await expect(plan).toContainText("Substitute TDF with ABC (ABC/3TC/DTG) once viral load suppression is confirmed.");
  const table = plan.getByRole("table");
  await expect(table.getByRole("columnheader")).toHaveText(["Problem", "AI suggests", "About your plan", "Verdict"]);
  const first = table.getByRole("row").nth(1);
  await expect(first).toContainText("Kidney function falling on TDF");
  await expect(first).toContainText("Your plan continues TLD.");
  await expect(first).toContainText("≠ Differs from your plan");
  // No verdict from the AI: no mark, and no note that could read as agreement.
  const third = table.getByRole("row").nth(3);
  await expect(third).toContainText("Not assessed");
  await expect(third).not.toContainText("Something the screen leaves out.");
  await expect(plan.getByRole("list", { name: "Monitoring" })).toContainText("Viral load now, before any switch");
  await expect(plan.getByRole("list", { name: "Counselling" })).toContainText("Avoid ibuprofen; paracetamol for pain");

  // A good plan: no "try again"; the plan step opens it again with no new call.
  await expect(tray(page)).toContainText("To change it, go back to Clinical notes.");
  await expect(tray(page).getByRole("button", { name: "Compare plans" })).toHaveCount(0);
  await tray(page).getByRole("button", { name: "Go to finalize" }).click();
  await tray(page).getByRole("button", { name: "Plan, done" }).click();
  await expect(plan).toBeVisible();
  expect(calls).toHaveLength(1);
});

test("a flagged plan shows the backend's warning, and can be tried again", async ({ page }) => {
  await checkedVisit(page);
  await standIn(page, { json: { ...PLAN, issues: ["missing_monitoring"], issues_note: "This plan failed the app's own checks. Treat it with care." } });
  await tray(page).getByRole("button", { name: "Compare plans" }).click();
  await expect(page.getByRole("main")).toContainText("This plan failed the app's own checks. Treat it with care.");
  await expect(tray(page).getByRole("button", { name: "Compare plans" })).toBeVisible();
});

test("a failed plan shows the backend's sentence, never the details, and can be tried again", async ({ page }) => {
  await checkedVisit(page);
  const failed = { ...PLAN, outcome: "failed", regimen: null, items: [], monitoring: [], counselling: [], error: "The management plan could not be produced." };
  const calls = await standIn(page, { json: failed });
  await tray(page).getByRole("button", { name: "Compare plans" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("The management plan could not be produced.");
  await tray(page).getByRole("button", { name: "Compare plans" }).click();
  await expect.poll(() => calls.length).toBe(2);
});

test("too many checks and plans this minute: the backend's reason is shown", async ({ page }) => {
  await checkedVisit(page);
  await standIn(page, { status: 429, json: { detail: "Too many visit checks: wait a moment and try again." } });
  await tray(page).getByRole("button", { name: "Compare plans" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Too many visit checks: wait a moment and try again.");
  await expect(tray(page).getByRole("button", { name: "Compare plans" })).toBeVisible();
});

test("a reopened visit brings its saved plan: the plan step is done and opens it with no new request", async ({ page }) => {
  await checkedVisit(page);
  await page.route("**/api/visits/*", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const reply = await route.fetch();
    await route.fulfill({ response: reply, json: { ...(await reply.json()), plan: PLAN } });
  });
  const calls = await standIn(page, { json: PLAN });
  await expect(page).toHaveURL(/[?&]visit=/); // the address names the saved visit once it is saved
  await page.reload();
  await expect(page.getByRole("region", { name: "Check results" })).toBeVisible();
  await tray(page).getByRole("button", { name: "Plan, done" }).click();
  await expect(page.getByRole("region", { name: "AI plan vs your plan" })).toContainText("Kidney function falling on TDF");
  expect(calls).toHaveLength(0);
});

test("a refused retry keeps the flagged plan on screen, under the refusal", async ({ page }) => {
  await checkedVisit(page);
  await standIn(page, { json: { ...PLAN, issues: ["missing_monitoring"], issues_note: "This plan failed the app's own checks. Treat it with care." } });
  await tray(page).getByRole("button", { name: "Compare plans" }).click();
  await expect(page.getByRole("main")).toContainText("This plan failed the app's own checks.");
  await page.unroute("**/api/visits/*/plan");
  await standIn(page, { status: 429, json: { detail: "Too many visit checks: wait a moment and try again." } });
  await tray(page).getByRole("button", { name: "Compare plans" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Too many visit checks: wait a moment and try again.");
  await expect(page.getByRole("region", { name: "AI plan vs your plan" })).toContainText("Kidney function falling on TDF");
});
