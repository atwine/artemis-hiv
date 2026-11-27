// Running a visit check in the browser tests: with the rule checks only. The AI review box starts
// on (owner, 2026-11-27), so it is switched off first; no test ever calls a model.
import type { Page } from "@playwright/test";

export async function runRuleChecks(page: Page) {
  await page.getByRole("checkbox", { name: "AI review" }).uncheck();
  await page.getByRole("region", { name: "Visit steps" }).getByRole("button", { name: "Run checks" }).click();
}
