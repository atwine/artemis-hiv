// One visit, start to end, in a real browser against the real backend and database:
// open a patient, run the rule checks (no AI review, so nothing is spent), review the alert on its
// own screen, override it, then change the decision to accept.
// P001 (John Doe) is on TDF with an old creatinine result, so the rule check raises one alert.
import { execFileSync } from "node:child_process";
import path from "node:path";

import { expect, test } from "@playwright/test";

import type { VisitCheck } from "../src/lib/api/client";
import { SOURCE_LABEL } from "../src/lib/alerts";

const DISCLAIMER = "Decision support only. Clinician retains final authority. Synthetic data only.";
const FINALIZE_BLOCKED =
  "Finalize is disabled until all alerts are acknowledged or overridden with a reason (the reason 'Other (say why)' needs a comment).";
const CREATININE = "Creatinine monitoring overdue while on TDF";

test("a clinician runs the checks, reviews the alert on its own screen and decides it", async ({ page }) => {
  await page.goto("/");
  const footer = page.getByRole("contentinfo");
  await expect(footer).toContainText(DISCLAIMER);
  await page.getByRole("main").getByRole("link", { name: "John Doe" }).click();

  await expect(page.getByRole("heading", { name: "John Doe", level: 1 })).toBeVisible();

  // Before the checks (S2): the record as recorded, units never converted (owner, 2026-11-26).
  const record = page.getByRole("region", { name: "From his record" });
  await expect(record.getByRole("definition").filter({ hasText: "88 umol/L, 1 Oct 2024" })).toBeVisible();
  await expect(record.getByRole("definition").filter({ hasText: "40 copies/mL, 1 Oct 2025" })).toBeVisible();
  await expect(record.getByRole("definition").filter({ hasText: "No new complaints. Appears well." })).toBeVisible();
  await record.getByRole("button", { name: "Full record, 2 lab results" }).click();
  await expect(record.getByRole("table", { name: "Lab results" }).getByRole("row")).toHaveCount(3); // header + 2
  await record.getByRole("button", { name: "Back to the summary" }).click();
  const notes = page.getByRole("textbox", { name: "Clinical notes" });
  await expect(notes).toHaveValue("Routine follow-up. No issues."); // today's note from the record
  await notes.fill("Routine follow-up. No complaints. Continue TLD, 3-month refill.");
  await expect(page.getByRole("checkbox", { name: "AI review" })).not.toBeChecked();
  const tray = page.getByRole("region", { name: "Visit steps" });
  // Hold the check for 1.5 s before it goes to the real backend, so the running screen is always
  // there to see, however fast the backend answers.
  await page.route("**/api/patients/*/visits", async (route) => {
    await new Promise((r) => setTimeout(r, 1500));
    await route.continue();
  });
  const replyPromise = page.waitForResponse((r) => r.url().endsWith("/api/patients/P001/visits") && r.request().method() === "POST");
  await tray.getByRole("button", { name: "Run checks" }).click();
  // While they run (S3): the first check of a run loads the search model, so this shows for a while.
  await expect(page.getByRole("heading", { name: "Checking John's visit. Rule checks only." })).toBeVisible();
  await expect(page.getByRole("region", { name: "Checks running" })).toContainText("His regimen, 2 lab results, today's notes.");

  // The results screen first (owner, 2026-11-26): the API's banners and one row per alert.
  const results = page.getByRole("region", { name: "Check results" });
  // The first check of a run loads the search model (and builds the index if it isn't built).
  await expect(results.or(page.getByRole("main").getByRole("alert"))).toBeVisible({ timeout: 5 * 60 * 1000 });
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  const reply = (await (await replyPromise).json()) as VisitCheck;
  await expect(results.getByRole("status").filter({ hasText: /^AMBER: \d+ alert\(s\) to consider\.$/ })).toBeVisible();
  await expect(results.getByText(FINALIZE_BLOCKED)).toBeVisible();
  expect(reply.disclaimer).toBe(DISCLAIMER); // the footer's copy is the API's
  await expect(footer).toContainText(DISCLAIMER);

  // The source tag's words are the API heading's own (the design's split, owner 2026-11-26).
  for (const card of reply.cards) {
    expect(card.extension.heading).toBe(`Alert (${SOURCE_LABEL[card.extension.kind]}): ${card.summary}`);
  }

  const rows = results.getByRole("list", { name: "Alerts" }).getByRole("listitem");
  await expect(rows).toHaveCount(reply.cards.length);
  const row = rows.filter({ hasText: CREATININE });
  await expect(row).toContainText("To review");

  // One alert per screen.
  await tray.getByRole("button", { name: "Review alert 1" }).click();
  const alert = page.getByRole("region", { name: "Alert 1" });
  await expect(alert.getByRole("heading", { level: 2 })).toContainText(CREATININE);
  await expect(alert.getByText("Rule check", { exact: true })).toBeVisible();
  await expect(alert.getByText("Related passages (found by a search for this alert)")).toBeVisible();
  // The patient's value the alert is about, as recorded (the design's "52 eGFR" box).
  const values = alert.getByRole("list", { name: "Patient values" });
  await expect(values).toContainText("John, 1 Oct 2024");
  await expect(values).toContainText("88");
  await expect(values).toContainText("umol/L");
  await expect(alert.getByText(/^Uganda HIV Guidelines 2022 · p\. \d+$/).first()).toBeVisible();
  const whole = alert.getByRole("button", { name: "Show the whole passage" });
  await expect(whole).toHaveAttribute("aria-expanded", "false");
  await whole.click();
  await expect(alert.getByRole("button", { name: "Show less" })).toHaveAttribute("aria-expanded", "true");
  await expect(tray).toContainText("Alert 1 of 1. Does it apply to John today?");

  // Override: one tap per reason, from the card's own list; "Other (say why)" asks for a comment.
  await tray.getByRole("button", { name: "Override" }).click();
  await expect(page.getByRole("heading", { level: 2 })).toContainText("Why does it not apply?");
  const reasons = page.getByRole("list", { name: "Override reasons" }).getByRole("button");
  await expect(reasons).toHaveCount(reply.cards[0].overrideReasons?.length ?? 0);
  await reasons.filter({ hasText: "Other (say why)" }).click();
  const saveOverride = tray.getByRole("button", { name: "Save override" });
  await expect(saveOverride).toBeDisabled();
  await page.getByRole("textbox", { name: "Why does it not apply?" }).fill("Result from a private lab, not in the file.");
  await saveOverride.click();

  // Saved by the backend: back on the results screen, the row says so and the finalize note goes.
  await expect(row).toContainText("Overridden: Other (say why)");
  await expect(results.getByText(FINALIZE_BLOCKED)).toBeHidden();
  await expect(tray.getByText(/^Alert \d+, to do$/)).toHaveCount(0); // every dot is done

  // A decision can be changed: the latest one counts.
  await row.getByRole("button").click();
  await expect(tray).toContainText("You overrode it: Other (say why).");
  await tray.getByRole("button", { name: "Accept alert" }).click();
  await expect(row).toContainText("Accepted");
});

// A visit with no alerts (S7b): the API's banner as the headline, and what was checked, so a quiet
// screen never looks like a skipped one. Jane Roe (P002) raises no alert; the AI review is off.
test("a quiet visit says what was checked", async ({ page }) => {
  await page.goto("/patients/P002");
  await page.getByRole("region", { name: "Visit steps" }).getByRole("button", { name: "Run checks" }).click();
  const quiet = page.getByRole("region", { name: "Check results" });
  await expect(quiet).toBeVisible({ timeout: 5 * 60 * 1000 });
  await expect(quiet.getByRole("heading", { level: 2 })).toHaveText(
    "No rule check was triggered. The AI review was switched off for this run.",
  );
  const checked = quiet.getByRole("list", { name: "What was checked" });
  await expect(checked).toContainText("1regimen");
  await expect(checked).toContainText("3medicines");
  await expect(checked).toContainText("3lab results");
  await expect(checked).toContainText("2notes");
  await expect(page.getByText("GREEN", { exact: true })).toBeVisible(); // the status chip
});

// Both source tags, not only the rule one a no-AI run can show: the words are the API heading's own
// (artemis/screen_text.alert_heading), so the design's split shows the same words.
test("the source tags are the words of the API's alert headings", () => {
  const script = [
    "import sys, json",
    "sys.path.insert(0, sys.argv[1])",
    "from artemis.rules.checks import Alert",
    "from artemis.screen_text import alert_heading",
    "print(json.dumps({k: alert_heading(Alert('a', 'T', '', {}, '', source=k)) for k in ('ai', 'rule')}))",
  ].join("\n");
  const repo = path.resolve(__dirname, "..", "..");
  const headings = JSON.parse(execFileSync(process.env.PYTHON || "python", ["-c", script, repo], { encoding: "utf8" }));
  for (const kind of ["ai", "rule"] as const) expect(headings[kind]).toBe(`Alert (${SOURCE_LABEL[kind]}): T`);
});
