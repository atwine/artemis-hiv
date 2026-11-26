// One visit, start to end, in a real browser against the real backend and database:
// open a patient, run the rule checks (no AI review, so nothing is spent), decide every alert.
// P001 (John Doe) is on TDF with an old creatinine result, so the rule check raises an alert.
import { expect, test } from "@playwright/test";

const DISCLAIMER = "Decision support only. Clinician retains final authority. Synthetic data only.";
const FINALIZE_BLOCKED =
  "Finalize is disabled until all alerts are acknowledged or overridden with a reason (the reason 'Other' needs a comment).";
const CREATININE_ALERT = "Alert (Rule check): Creatinine monitoring overdue while on TDF";

test("a clinician runs the rule checks on a patient and decides every alert", async ({ page }) => {
  await page.goto("/");
  const footer = page.getByRole("contentinfo");
  await expect(footer).toContainText(DISCLAIMER);
  await page.getByRole("main").getByRole("link", { name: "John Doe" }).click();

  await expect(page.getByRole("heading", { name: "John Doe", level: 1 })).toBeVisible();
  const notes = page.getByRole("textbox", { name: "Clinical notes" });
  await expect(notes).toHaveValue("Routine follow-up. No issues."); // today's note from the record
  await notes.fill("Routine follow-up. No complaints. Continue TLD, 3-month refill.");
  await expect(page.getByRole("checkbox", { name: "AI review" })).not.toBeChecked();
  const tray = page.getByRole("region", { name: "Visit steps" });
  const reply = page.waitForResponse((r) => r.url().endsWith("/api/patients/P001/visits") && r.request().method() === "POST");
  await tray.getByRole("button", { name: "Run checks" }).click();

  // The banners, card headings, disclaimer and finalize note are the API's own words.
  const results = page.getByRole("region", { name: "Check results" });
  // The first check of a run loads the search model (and builds the index if it isn't built).
  await expect(results.or(page.getByRole("main").getByRole("alert"))).toBeVisible({ timeout: 5 * 60 * 1000 });
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  await expect(results.getByRole("status").filter({ hasText: /^AMBER: \d+ alert\(s\) to consider\.$/ })).toBeVisible();
  // The footer's disclaimer, shown before any check, is the one the API sends.
  expect((await (await reply).json()).disclaimer).toBe(DISCLAIMER);
  await expect(footer).toContainText(DISCLAIMER);
  await expect(results.getByText(FINALIZE_BLOCKED)).toBeVisible();

  const cards = results.getByRole("article");
  const count = await cards.count();
  expect(count).toBeGreaterThan(0);
  const creatinine = cards.filter({ has: page.getByRole("heading", { name: CREATININE_ALERT }) });
  await expect(creatinine).toHaveCount(1);
  await expect(creatinine.getByText("Related passages (found by a search for this alert)")).toBeVisible();

  const save = tray.getByRole("button", { name: "Save decisions" });
  await expect(save).toBeDisabled(); // nothing decided yet

  // Override the creatinine alert. "Other" needs a comment before it can be saved.
  await creatinine.getByRole("radio", { name: "Override" }).check();
  await creatinine.getByRole("combobox", { name: "Override reason" }).selectOption("Other");
  for (let i = 0; i < count; i++) {
    const card = cards.nth(i);
    if (!(await card.getByRole("radio", { name: "Override" }).isChecked())) {
      await card.getByRole("radio", { name: "Acknowledge" }).check();
    }
  }
  await expect(save).toBeDisabled();
  await creatinine.getByRole("textbox", { name: "Comment" }).fill("Result from a private lab, not in the file.");
  await expect(save).toBeEnabled();
  await save.click();

  // The backend saved them: each card shows the decision it recorded, and its reply says every
  // alert is decided, so the finalize note goes.
  await expect(creatinine.getByText(/^Saved: Override \(Other\)/)).toBeVisible();
  for (let i = 0; i < count; i++) await expect(cards.nth(i).getByText(/^Saved: /)).toBeVisible();
  await expect(results.getByText(FINALIZE_BLOCKED)).toBeHidden();
  await expect(tray.getByRole("list", { name: "Alerts" }).getByRole("listitem")).toHaveCount(count);
  await expect(tray.getByText(/^Alert \d+, to do$/)).toHaveCount(0); // every dot is done
});
