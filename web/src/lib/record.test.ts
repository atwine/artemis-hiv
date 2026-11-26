import assert from "node:assert/strict";
import { test } from "node:test";

import { asSentence, checkReads, checkedCounts, firstSentence, labCount, labRows, longDate, otherMedicines, possessive, previousArt, todaySummary } from "./record.ts";

test("a lab row: the latest result with its unit as recorded, and the earliest for comparison", () => {
  const rows = labRows(
    {
      creatinine: [
        { date: "2020-03-10", value: "0.9", unit: "mg/dL", source: "record" },
        { date: "2026-02-24", value: "1.4", unit: "mg/dL", source: "record" },
        { date: "2022-04-05", value: "1.1", unit: "mg/dL", source: "record" },
      ],
      viral_load: [{ date: "2026-05-12", value: "<50", unit: "copies/mL", source: "record" }],
      egfr: [{ date: "2026-02-24", value: "52", unit: "mL/min/1.73 m²", source: "record" }],
    },
    "2026-02-24",
  );
  assert.deepEqual(rows, [
    { label: "Creatinine", text: "1.4 mg/dL today · 0.9 in 2020" },
    { label: "Viral load", text: "<50 copies/mL, 12 May 2026" },
    { label: "eGFR", text: "52 mL/min/1.73 m² today" },
  ]);
});

test("a lab with no unit recorded shows the value alone, never a made-up unit", () => {
  assert.deepEqual(labRows({ urine_protein: [{ date: "2026-02-24", value: "1+", unit: "", source: "record" }] }, "2026-02-24"), [
    { label: "Urine protein", text: "1+ today" },
  ]);
});

test("counting lab results", () => {
  assert.equal(labCount({ a: [{ date: "2020-01-01", value: "1", unit: "", source: "" }], b: [] }), 1);
});

test("previous ART: regimens that ended, with their years", () => {
  assert.equal(
    previousArt([
      { regimen: ["AZT", "3TC", "NVP"], start_date: "2018-01-01", end_date: "2020-06-01" },
      { regimen: ["TDF", "3TC", "DTG"], start_date: "2020-06-01", end_date: null },
    ]),
    "AZT/3TC/NVP, 2018–2020",
  );
  assert.equal(previousArt([{ regimen: ["TDF", "3TC", "DTG"], start_date: "2023-01-10", end_date: null }]), null);
});

test("other medicines, or none", () => {
  assert.equal(otherMedicines(["Ibuprofen 400 mg", "Cotrimoxazole 960 mg"]), "Ibuprofen 400 mg; Cotrimoxazole 960 mg");
  assert.equal(otherMedicines([]), null);
});

test("dates and the record's owner", () => {
  assert.equal(longDate("2024-10-01"), "1 Oct 2024");
  assert.equal(possessive("F"), "her");
  assert.equal(possessive("M"), "his");
  assert.equal(possessive(""), "the");
});

test("today's summary: the complaints and examination as written, each ending as a sentence", () => {
  assert.equal(todaySummary({ complaints_symptoms: "No new complaints", examination_findings: "Appears well" }), "No new complaints. Appears well.");
  assert.equal(todaySummary({ complaints_symptoms: "  ", examination_findings: 3 }), null);
  assert.equal(asSentence("Done!"), "Done!");
});

test("what the checks read, from the record (S3)", () => {
  assert.equal(
    checkReads({ sex: "F", other_medications: ["Ibuprofen 400 mg"], labs: { cr: [{ date: "2026-01-01", value: "1", unit: "", source: "" }, { date: "2025-01-01", value: "1", unit: "", source: "" }] }, lab_notes: [] }, true),
    "Her regimen, 1 other medicine, 2 lab results, today's notes, Ugandan guideline passages.",
  );
  assert.equal(checkReads({ sex: "M", other_medications: [], labs: {}, lab_notes: [{ date: null, source: "", text: "x" }] }, false), "His regimen, lab notes, today's notes.");
});

test("what was checked (S7b): counts from the record", () => {
  assert.deepEqual(
    checkedCounts({
      art_regimen_current: ["TDF", "3TC", "DTG"],
      other_medications: ["Ibuprofen 400 mg"],
      labs: { vl: [{ date: "2025-01-01", value: "40", unit: "", source: "" }] },
      lab_notes: [{ date: null, source: "", text: "x" }],
      visits: [{}, {}],
      today_encounter: { note: "Stable." },
    }),
    [
      { n: 1, label: "regimen" },
      { n: 4, label: "medicines" },
      { n: 1, label: "lab result" },
      { n: 1, label: "lab note" },
      { n: 3, label: "notes" },
    ],
  );
});

test("a banner's first sentence, for the headline's bold part", () => {
  assert.deepEqual(firstSentence("GREEN: no alerts. The rule checks and the AI review found nothing."), [
    "GREEN: no alerts.",
    "The rule checks and the AI review found nothing.",
  ]);
  assert.deepEqual(firstSentence("One sentence only."), ["One sentence only.", ""]);
});
