// The clinic day (Paper FINAL S1 and S1b) against the real backend: today's appointments from
// GET /api/clinic-day, a visit moving from Waiting to Needs you once its checks run, and
// "Continue review" reopening the saved visit (GET /api/visits/{id}) without a new check.
import { expect, test } from "@playwright/test";

import { runRuleChecks } from "./checks";

import { E2E } from "./ports";

test("the clinic day shows who is waiting, and a checked visit moves to Needs you", async ({ page }) => {
  await page.goto("/");

  // The clinic and clinician come from the API (no logins yet: the demo day's values).
  const top = page.getByRole("banner");
  await expect(top).toContainText("Demo ART Clinic · Room 3");
  await expect(top).toContainText("Dr. A. Okello");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Thursday 26 Nov.");

  const waiting = page.getByRole("region", { name: "Waiting" });
  await expect(waiting.getByRole("link", { name: /Sam Kato/ })).toBeVisible();

  // Run Sam Kato's checks (rules only), then go back to the day.
  await waiting.getByRole("link", { name: /Sam Kato/ }).click();
  await expect(page.getByRole("heading", { name: "Sam Kato", level: 1 })).toBeVisible();
  await runRuleChecks(page);
  await expect(page.getByRole("region", { name: "Check results" })).toBeVisible({ timeout: 5 * 60 * 1000 });
  await page.getByRole("link", { name: "← Back to day" }).click();

  const needsYou = page.getByRole("region", { name: "Needs you" });
  const sam = needsYou.getByRole("listitem").filter({ hasText: "Sam Kato" });
  await expect(sam).toBeVisible();
  await expect(sam).toContainText(/AMBER|RED|GREEN|INCOMPLETE/);
  await expect(waiting).not.toContainText("Sam Kato");

  // The first visit that needs you carries the one main button; it reopens the saved visit.
  await needsYou.getByRole("link", { name: "Continue review" }).click();
  await expect(page.getByRole("heading", { name: "Sam Kato", level: 1 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Check results" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Checks running" })).toHaveCount(0); // no new check

  // The list view: the same day, top to bottom, and the choice is kept in the address.
  await page.getByRole("link", { name: "← Back to day" }).click();
  await page.getByRole("link", { name: "List" }).click();
  await expect(page).toHaveURL(/view=list/);
  const rows = page.getByRole("list", { name: "Today's visits" }).getByRole("listitem");
  await expect(rows.first()).toContainText("08:40");
  await expect(rows.filter({ hasText: "Sam Kato" })).toContainText(/AMBER|RED|GREEN|INCOMPLETE/);
});

test("blue links above the date step to the clinic days around it, keeping the view", async ({ page }) => {
  // A made-up case booked on a day after every other one, so that day has nothing after it.
  const added = await page.request.post(`${E2E.apiUrl}/api/patients`, {
    data: { patient_id: "P190", name: "Esther Last", visit_date: "2099-12-31", appointment_time: "09:00" },
  });
  expect(added.ok()).toBe(true);

  // The demo day is the first clinic day: a link to the next one only.
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Thursday 26 Nov.");
  const steps = page.getByRole("navigation", { name: "Other clinic days" });
  await expect(steps.getByRole("link")).toHaveCount(1);
  await steps.getByRole("link").click();
  await expect(page).toHaveURL(/\?date=2099-/);
  await expect(page.getByRole("heading", { level: 1 })).not.toContainText("26 Nov");

  // The last day, in the list view: a link back only, and stepping keeps the list.
  await page.goto("/?date=2099-12-31&view=list");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Thursday 31 Dec.");
  await expect(page.getByRole("list", { name: "Today's visits" })).toContainText("Esther Last");
  await expect(steps.getByRole("link")).toHaveCount(1);
  await steps.getByRole("link").click();
  await expect(page).toHaveURL(/view=list/);
  await expect(page.getByRole("heading", { level: 1 })).not.toContainText("31 Dec");

  // Switching to the board stays on the day shown.
  await page.goto("/?date=2099-12-31&view=list");
  await page.getByRole("link", { name: "Board" }).click();
  await expect(page).toHaveURL(/\?date=2099-12-31$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Thursday 31 Dec.");
});

// "Find a patient" (owner, 2026-11-27: "A, a find box"): any patient on record by name or ID, each
// match saying when it is booked on the day shown; a match opens the patient's visit. It works by
// keyboard: Tab from the box to a match, Enter to open it.
test("find a patient by name or ID, booked or not, with the mouse or the keyboard", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Thursday 26 Nov.");
  const find = page.getByRole("searchbox", { name: "Find a patient" });
  const matches = page.getByRole("list", { name: "Matching patients" });
  await expect(matches).toHaveCount(0); // nothing until something is typed

  await find.fill("kato");
  await expect(matches.getByRole("link")).toHaveCount(2); // any part of the name: Sam Kato and Joan Nakato
  await expect(matches).toContainText("Sam Kato");
  await expect(matches).toContainText("Joan Nakato");
  await expect(matches).toContainText("Thu 26 Nov 09:05");

  await find.fill("p001");
  await expect(matches).toContainText("John Doe");
  await expect(matches).toContainText("not booked Thu 26 Nov");
  await matches.getByRole("link", { name: /John Doe/ }).click();
  await expect(page).toHaveURL(/\/patients\/P001$/);
  await expect(page.getByRole("heading", { name: /John Doe/, level: 1 })).toBeVisible();

  await page.goto("/");
  await find.fill("nobody like this");
  await expect(page.getByText("No patient matches.")).toBeVisible();
  await find.fill("roe");
  await find.press("Tab");
  await expect(matches.getByRole("link", { name: /Jane Roe/ })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/patients\/P002$/);
});
