import assert from "node:assert/strict";
import { test } from "node:test";

import {
  addsTo,
  emptyDraft,
  formErrors,
  parseDraft,
  partOneProblems,
  unaddedMedicine,
  pickLists,
  timeProblem,
  toggleDrug,
  toNewCase,
  withShortcut,
  type CaseDraft,
} from "./new-case.ts";

const REGIMENS = [
  { choice: "TLD", drugs: ["TDF", "3TC", "DTG"] },
  { choice: "TLE", drugs: ["TDF", "3TC", "EFV"] },
  { choice: "TDF", drugs: ["TDF"] },
  { choice: "3TC", drugs: ["3TC"] },
  { choice: "DTG", drugs: ["DTG"] },
  { choice: "EFV", drugs: ["EFV"] },
  { choice: "LPV/r", drugs: ["LPV/r"] },
];

const grace = (over: Partial<CaseDraft> = {}): CaseDraft => ({
  ...emptyDraft("2026-11-27"),
  patientId: " P010 ",
  name: " Grace Atim ",
  age: "41",
  sex: "F",
  time: "11:00",
  visitType: "Routine review",
  drugs: ["TDF", "3TC", "DTG"],
  ...over,
});

test("the pick lists: single drugs as chips, combinations as shortcuts, in the backend's order", () => {
  assert.deepEqual(pickLists(REGIMENS), {
    drugs: ["TDF", "3TC", "DTG", "EFV", "LPV/r"],
    shortcuts: [
      { choice: "TLD", drugs: ["TDF", "3TC", "DTG"] },
      { choice: "TLE", drugs: ["TDF", "3TC", "EFV"] },
    ],
  });
});

test("tapping a drug picks it, tapping again drops it; a shortcut adds its drugs once", () => {
  assert.deepEqual(toggleDrug(["TDF"], "DTG"), ["TDF", "DTG"]);
  assert.deepEqual(toggleDrug(["TDF", "DTG"], "TDF"), ["DTG"]);
  assert.deepEqual(withShortcut(["3TC"], ["TDF", "3TC", "DTG"]), ["3TC", "TDF", "DTG"]);
});

test("the appointment time is HH:MM on a 24-hour clock, as the backend takes it", () => {
  for (const ok of ["00:00", "09:30", "11:00", "23:59"]) assert.equal(timeProblem(ok), null, ok);
  for (const bad of ["", "9:00", "24:00", "09:60", "09:00 ", "9.30"]) assert.notEqual(timeProblem(bad), null, bad);
});

test("part 1 needs an ID and a time before part 2", () => {
  assert.deepEqual(partOneProblems(grace()), []);
  assert.deepEqual(partOneProblems(grace({ patientId: "  ", time: "" })), [
    "Patient ID is required.", // the backend's own words
    "Give the appointment time as HH:MM, 24-hour (for example 09:30).",
  ]);
});

test("a medicine typed but not added stops part 1 until it is added or cleared (owner, 2026-11-27)", () => {
  assert.equal(unaddedMedicine("  "), null);
  assert.equal(
    unaddedMedicine(" Ibuprofen 400 mg, three times a day "),
    "Press + Add medicine to keep 'Ibuprofen 400 mg, three times a day', or clear the box.",
  );
});

test("previous ART needs both dates before part 2, in the backend's own words", () => {
  const past = (drugs: string[], start: string, end: string) => ({ drugs, start, end });
  assert.deepEqual(partOneProblems(grace({ previousArt: [past([], "", "")] })), []); // a blank row is left out
  assert.deepEqual(
    partOneProblems(grace({ previousArt: [past(["AZT"], "2016-03-01", "2019-08-15"), past(["TDF", "EFV"], "2019-08-15", "")] })),
    ["Previous ART, row 2: give a start and an end date."],
  );
});

test("the case goes to the backend as typed, trimmed, with blank rows and boxes left out", () => {
  const body = toNewCase(
    grace({
      medicines: ["Ibuprofen 400 mg, three times a day", "  "],
      previousArt: [
        { drugs: [], start: "", end: "" },
        { drugs: ["AZT", "3TC", "NVP"], start: "2016-03-01", end: "2019-08-15" },
      ],
      labs: [
        { test: "creatinine", date: "2026-11-27", value: "0.8", unit: "mg/dL" },
        { test: "viral_load", date: "2026-05-12", value: "<50", unit: "copies/mL" },
        { test: "", date: "", value: "", unit: "" },
      ],
      complaints: "None today",
      exam: "Unremarkable",
      note: "Routine review.",
    }),
  );
  assert.deepEqual(body, {
    patient_id: "P010",
    name: "Grace Atim",
    age_years: 41,
    sex: "F",
    visit_date: "2026-11-27",
    appointment_time: "11:00",
    visit_type: "Routine review",
    art_regimen: ["TDF", "3TC", "DTG"],
    other_medications: ["Ibuprofen 400 mg, three times a day"],
    previous_art: [{ regimen: ["AZT", "3TC", "NVP"], start_date: "2016-03-01", end_date: "2019-08-15" }],
    // A result dated on the visit day is today's; the backend uses this only to word its errors.
    labs: [
      { test: "creatinine", date: "2026-11-27", value: "0.8", unit: "mg/dL", when: "today" },
      { test: "viral_load", date: "2026-05-12", value: "<50", unit: "copies/mL", when: "previous" },
    ],
    complaints: "None today",
    examination_findings: "Unremarkable",
    prior_history: "",
    todays_note: "Routine review.",
  });
});

test("left blank: no name, age, sex or visit type is sent as null, never as an empty pick", () => {
  const body = toNewCase(grace({ name: "", age: "", sex: "", visitType: "" }));
  assert.equal(body.name, null);
  assert.equal(body.age_years, null);
  assert.equal(body.sex, null);
  assert.equal(body.visit_type, null);
  assert.equal(toNewCase(grace({ visitDate: "" })).visit_date, null); // the backend books it today
});

test("what the backend refused: its own reasons as sent, anything else as one plain line", () => {
  assert.deepEqual(formErrors("That patient ID is already in use."), ["That patient ID is already in use."]);
  assert.deepEqual(formErrors(["Row 1 (Creatinine): the value 'x' has no number in it."]), [
    "Row 1 (Creatinine): the value 'x' has no number in it.",
  ]);
  assert.deepEqual(formErrors([{ loc: ["body", "age_years"], msg: "Input should be a valid integer", type: "int_parsing" }]), [
    "The case wasn't saved: a field isn't in the form the server expects. Check the boxes and try again.",
  ]);
});

test("the tray says which clinic day the case joins", () => {
  assert.equal(addsTo("Grace Atim", "2026-11-27", "2026-11-27"), "Adds Grace to today's clinic day.");
  assert.equal(addsTo("Grace Atim", "2026-11-30", "2026-11-27"), "Adds Grace to the clinic day on Mon 30 Nov.");
  assert.equal(addsTo("", "2026-11-27", "2026-11-27"), "Adds the patient to today's clinic day.");
  assert.equal(addsTo("Grace", "", "2026-11-27"), "Adds Grace to today's clinic day."); // no date: the backend books today
});

test("a saved draft comes back only when it has the draft's shape", () => {
  const draft = grace({ labs: [{ test: "cd4", date: "2026-11-01", value: "350", unit: "cells/uL" }] });
  assert.deepEqual(parseDraft(JSON.stringify({ part: 2, draft })), { part: 2, draft });
  assert.equal(parseDraft("not json"), null);
  assert.equal(parseDraft(JSON.stringify({ part: 3, draft })), null);
  assert.equal(parseDraft(JSON.stringify({ part: 1, draft: { ...draft, drugs: "TDF" } })), null);
  assert.equal(parseDraft(JSON.stringify({ part: 1, draft: { ...draft, labs: [{ test: 1 }] } })), null);
  assert.equal(parseDraft(JSON.stringify({ part: 1, draft: { ...draft, extra: "x" } })), null);
});
