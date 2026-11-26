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
  await page.goto("/patients/P001"); // John Doe isn't on the demo day; opened directly

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
    if (route.request().method() !== "POST") return route.continue(); // only the check
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
  // The address now names the saved visit, so Back or a reload reopens it instead of a blank form.
  await expect(page).toHaveURL((url) => url.pathname === "/patients/P001" && url.searchParams.get("visit") === reply.visit_id);
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

  // Finalize asks first (owner's decision 6): a one-line confirm in the tray; "Go back" changes nothing.
  await tray.getByRole("button", { name: "Finalize visit" }).click();
  await expect(tray).toContainText("Finalize John's visit? Decisions can't be changed after this.");
  await tray.getByRole("button", { name: "Go back" }).click();
  await expect(tray).not.toContainText("Decisions can't be changed after this.");
  await tray.getByRole("button", { name: "Finalize visit" }).click();
  await tray.getByRole("button", { name: "Finalize", exact: true }).click();

  // The saved visit record (S6b): what was checked and what was decided, read only.
  const visitRecord = page.getByRole("region", { name: "Visit record" });
  await expect(visitRecord.getByRole("heading", { level: 2 })).toContainText(/^Visit finalized \d\d:\d\d\./);
  await expect(visitRecord.getByRole("list", { name: "Decisions" })).toContainText(/Accepted \d\d:\d\d/);
  await expect(page.getByText(/^AMBER · FINALIZED$/)).toBeVisible();
  await expect(tray.getByRole("button", { name: "Accept alert" })).toHaveCount(0);
  await page.reload(); // a reload shows the record, never a new check
  await expect(page.getByRole("region", { name: "Visit record" })).toBeVisible();
  await expect(tray.getByRole("button", { name: "Run checks" })).toHaveCount(0);

  // Reopening a finalized visit shows its record, with no new check and no way to change it.
  await page.goto(`/patients/P001?visit=${reply.visit_id}`);
  await expect(page.getByRole("region", { name: "Visit record" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Checks running" })).toHaveCount(0);

  // Past checks sit in the record column before the next check (owner, 2026-11-26), newest first.
  await page.goto("/patients/P001");
  const past = page.getByRole("list", { name: "Past checks" });
  const finalized = past.getByRole("listitem").filter({ hasText: "Finalized" }).first();
  await expect(finalized).toContainText("AMBER");
  await finalized.getByRole("link").click();
  await expect(page.getByRole("region", { name: "Visit record" })).toBeVisible();
});

test("finalize stays locked until every alert has an answer", async ({ page }) => {
  await page.goto("/patients/P001");
  const tray = page.getByRole("region", { name: "Visit steps" });
  await tray.getByRole("button", { name: "Run checks" }).click();
  await expect(page.getByRole("region", { name: "Check results" })).toBeVisible({ timeout: 5 * 60 * 1000 });
  await tray.getByRole("button", { name: /^Finalize, / }).click(); // the tray's Finalize step ("Finalize, to do")
  const finalize = page.getByRole("region", { name: "Finalize" });
  await expect(finalize).toContainText(FINALIZE_BLOCKED); // the API's own words
  await expect(tray.getByRole("button", { name: "Finalize visit" })).toBeDisabled();
  await expect(tray).toContainText(/Finalize is locked\. 1 alert left to review\./);
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

// Too many checks in a minute (the backend's limit, 429): the screen shows the API's own words and
// keeps the note, so "Run checks" can simply be pressed again.
test("too many checks: the API's message, and the note kept", async ({ page }) => {
  const TOO_MANY = "Too many visit checks: wait a moment and try again."; // backend/main.py's detail
  await page.route("**/api/patients/*/visits", async (route) =>
    route.request().method() === "POST" ? route.fulfill({ status: 429, json: { detail: TOO_MANY }, headers: { "Retry-After": "30" } }) : route.continue(),
  );
  await page.goto("/patients/P001");
  const notes = page.getByRole("textbox", { name: "Clinical notes" });
  await notes.fill("Note written before the limit was hit.");
  await page.getByRole("region", { name: "Visit steps" }).getByRole("button", { name: "Run checks" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(TOO_MANY);
  await expect(notes).toHaveValue("Note written before the limit was hit.");
  await expect(page.getByRole("region", { name: "Visit steps" }).getByRole("button", { name: "Run checks" })).toBeEnabled();
});
