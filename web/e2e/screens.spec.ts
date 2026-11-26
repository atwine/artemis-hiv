// Screenshots of the website at the design's 1366 x 768, for checking it side by side with the
// Paper FINAL screens (docs/design/exports/phase5/). Runs only when asked:
//   ARTEMIS_SCREENS=1 npx playwright test screens
import path from "node:path";

import { expect, test } from "@playwright/test";

const OUT = path.resolve(__dirname, "..", "..", "docs", "design", "exports", "phase5");

test.skip(!process.env.ARTEMIS_SCREENS, "set ARTEMIS_SCREENS=1 to take the screenshots");

test("the shared frame, before and after the checks", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("main").getByRole("link", { name: "John Doe" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-0-patients.png") });

  await page.getByRole("main").getByRole("link", { name: "John Doe" }).click();
  await expect(page.getByRole("textbox", { name: "Clinical notes" })).toBeVisible();
  await page.screenshot({ path: path.join(OUT, "web-S2-before-checks.png") });

  await page.getByRole("region", { name: "Visit steps" }).getByRole("button", { name: "Run checks" }).click();
  await page.screenshot({ path: path.join(OUT, "web-S3-checks-running.png") });
  const results = page.getByRole("region", { name: "Check results" });
  await expect(results).toBeVisible({ timeout: 5 * 60 * 1000 });
  await page.screenshot({ path: path.join(OUT, "web-S4-results.png") });
});
