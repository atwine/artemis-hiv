// The clinic day (Paper FINAL S1 and S1b) against the real backend: today's appointments from
// GET /api/clinic-day, a visit moving from Waiting to Needs you once its checks run, and
// "Continue review" reopening the saved visit (GET /api/visits/{id}) without a new check.
import { expect, test } from "@playwright/test";

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
  await page.getByRole("region", { name: "Visit steps" }).getByRole("button", { name: "Run checks" }).click();
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
