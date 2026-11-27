// Adding a patient case (Paper FINAL S8a and S8b) against the real backend: part 1 (who, when,
// the regimen, other medicines and previous ART), the draft surviving a reload, part 2 (labs and today's
// three intake boxes and notes), and the saved case booked on its clinic day. The case is booked on a day far ahead, so
// the board's default day (today, else the latest before it) stays the 26 Nov demo day for the
// other tests.
import { expect, test, type Page } from "@playwright/test";

import { E2E } from "./ports";

const VISIT_DATE = "2099-01-05";

const tray = (page: Page) => page.getByRole("region", { name: "New case steps" });
const regimen = (page: Page) => page.getByRole("region", { name: "Current ART regimen" });

test("a new case: part 1, a reload keeps the draft, part 2, then it is saved and booked", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Add patient case" }).click();
  await expect(page).toHaveURL(/\/cases\/new$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("New patient case");

  await page.getByLabel("ID", { exact: true }).fill("P100");
  await page.getByLabel("Name", { exact: true }).fill("Grace Atim");
  await page.getByLabel("Age", { exact: true }).fill("41");
  await page.getByLabel("Sex", { exact: true }).selectOption({ label: "Female" });
  await page.getByLabel("Visit date", { exact: true }).fill(VISIT_DATE);
  await page.getByLabel("Time", { exact: true }).fill("11:00");
  await page.getByLabel("Visit type", { exact: true }).selectOption("Routine review");

  // The shortcut ticks its three drugs; each drug is a toggle.
  await regimen(page).getByRole("button", { name: /^TLD = TDF\/3TC\/DTG/ }).click();
  for (const drug of ["TDF", "3TC", "DTG"]) {
    await expect(regimen(page).getByRole("button", { name: drug, exact: true })).toHaveAttribute("aria-pressed", "true");
  }
  await expect(regimen(page).getByRole("button", { name: "EFV", exact: true })).toHaveAttribute("aria-pressed", "false");

  // Typed but not added: part 2 waits until it is added or the box is cleared.
  await page.getByRole("textbox", { name: "Other medicine", exact: true }).fill("Ibuprofen 400 mg, three times a day");
  await tray(page).getByRole("button", { name: "Next: labs and clinical notes" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Press + Add medicine to keep 'Ibuprofen 400 mg, three times a day', or clear the box.",
  );
  await page.getByRole("button", { name: "Add medicine" }).click();
  await expect(page.getByRole("list", { name: "Other medicines" })).toContainText("Ibuprofen 400 mg, three times a day");

  // Previous ART: tap its drugs, then both dates; part 2 waits for the end date.
  await page.getByRole("button", { name: "Add previous ART, with dates" }).click();
  const pastDrugs = page.getByRole("group", { name: "Previous ART 1 drugs" });
  for (const drug of ["AZT", "3TC", "NVP"]) await pastDrugs.getByRole("button", { name: drug, exact: true }).click();
  await page.getByLabel("Previous ART 1 from", { exact: true }).fill("2016-03-01");
  await tray(page).getByRole("button", { name: "Next: labs and clinical notes" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Previous ART, row 1: give a start and an end date.");
  await page.getByLabel("Previous ART 1 to", { exact: true }).fill("2019-08-15");

  // Saved as a draft as you type: a reload brings it all back.
  await page.reload();
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue("Grace Atim");
  await expect(page.getByLabel("Time", { exact: true })).toHaveValue("11:00");
  await expect(regimen(page).getByRole("button", { name: "DTG", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("list", { name: "Other medicines" })).toContainText("Ibuprofen");
  await expect(pastDrugs.getByRole("button", { name: "NVP", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("Previous ART 1 to", { exact: true })).toHaveValue("2019-08-15");

  await tray(page).getByRole("button", { name: "Next: labs and clinical notes" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Grace Atim");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("P100 · 41 F · TDF/3TC/DTG");
  await expect(tray(page)).toContainText("Adds Grace to the clinic day on Mon 5 Jan.");

  await page.getByLabel("Result 1 test").selectOption({ label: "Creatinine" }); // the API's list-ready name
  await page.getByLabel("Result 1 date").fill("2098-12-20");
  await page.getByLabel("Result 1 value").fill("0.8");
  await page.getByLabel("Result 1 unit").selectOption("mg/dL");
  await page.getByLabel("Complaints", { exact: true }).fill("Knee pain for two weeks");
  await page.getByLabel("Exam findings", { exact: true }).fill("Unremarkable");
  await page.getByLabel("Clinical notes", { exact: true }).fill("Routine review. Knee pain for two weeks, taking ibuprofen.");

  // Saving lands on the new patient's visit (owner, 2026-11-27).
  await tray(page).getByRole("button", { name: "Save case" }).click();
  await expect(page).toHaveURL(/\/patients\/P100$/, { timeout: 30 * 1000 });
  await expect(page.getByRole("heading", { name: "Grace Atim", level: 1 })).toBeVisible();

  // Saved, with what was typed, and booked at 11:00 on its day.
  const saved = await (await page.request.get(`${E2E.apiUrl}/api/patients/P100`)).json();
  expect(saved.name).toBe("Grace Atim");
  expect(saved.art_regimen_current).toEqual(["TDF", "3TC", "DTG"]);
  expect(saved.today_encounter.note).toContain("Knee pain");
  expect(saved.intake).toEqual(
    expect.objectContaining({ complaints_symptoms: "Knee pain for two weeks", examination_findings: "Unremarkable", prior_history: "" }),
  );
  expect(saved.regimen_history).toEqual([expect.objectContaining({ start_date: "2016-03-01", end_date: "2019-08-15" })]);
  const day = await (await page.request.get(`${E2E.apiUrl}/api/clinic-day?date=${VISIT_DATE}`)).json();
  expect(day.appointments).toContainEqual(expect.objectContaining({ patient_id: "P100", time: "11:00" }));

  // The draft is gone once the case is saved.
  await page.goto("/cases/new");
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue("");
});

test("an ID already in use: the backend's reason is shown and nothing is lost", async ({ page }) => {
  await page.goto("/cases/new");
  await page.getByLabel("ID", { exact: true }).fill("P001");
  await page.getByLabel("Name", { exact: true }).fill("Copy of John");
  await page.getByLabel("Visit date", { exact: true }).fill(VISIT_DATE);
  await page.getByLabel("Time", { exact: true }).fill("12:00");
  await tray(page).getByRole("button", { name: "Next: labs and clinical notes" }).click();
  await page.getByLabel("Clinical notes", { exact: true }).fill("A note that must survive the refusal.");
  await tray(page).getByRole("button", { name: "Save case" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("That patient ID is already in use.");
  await expect(page.getByLabel("Clinical notes", { exact: true })).toHaveValue("A note that must survive the refusal.");

  // The reason is about part 1's ID box: it stays on screen there.
  await page.getByRole("button", { name: "← Part 1" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("That patient ID is already in use.");
  await expect(page.getByLabel("ID", { exact: true })).toHaveValue("P001");
});

test("part 2 waits for an ID and a time", async ({ page }) => {
  await page.goto("/cases/new");
  await tray(page).getByRole("button", { name: "Next: labs and clinical notes" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Patient ID is required.");
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Give the appointment time as HH:MM");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("New patient case");
});
