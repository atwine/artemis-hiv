import assert from "node:assert/strict";
import { test } from "node:test";

import type { DayAppointment } from "./day.ts";
import { decisionLine, nextPatient, stillToReview } from "./visit.ts";

const appt = (patient_id: string, time: string, state: DayAppointment["state"]): DayAppointment => ({
  time, patient_id, name: `${patient_id} Name`, age_years: 30, sex: "F", regimen: "TLD", state,
  visit_id: null, status: null, ai_review: null, ai_review_label: null, ai_review_card_label: null, alert_count: 0, reviewed_count: 0, finalized_at: null,
});

test("a decision in the record: what was decided, when, and why", () => {
  assert.match(decisionLine({ alert_id: "a", action: "Acknowledge", reason: "", comment: "", saved_at: "2026-11-26T07:47:00Z" }), /^Accepted \d\d:\d\d$/);
  assert.match(
    decisionLine({ alert_id: "a", action: "Override", reason: "Already done, not documented", comment: "x", saved_at: "2026-11-26T07:49:00Z" }),
    /^Overridden \d\d:\d\d · Already done, not documented$/,
  );
});

test("the next patient: the first not finalized after this one, else before it", () => {
  const day = [appt("P004", "08:40", "done"), appt("P005", "09:30", "needs_you"), appt("P006", "09:50", "needs_you"), appt("P007", "10:10", "waiting")];
  assert.equal(nextPatient(day, "P005")?.patient_id, "P006");
  assert.equal(nextPatient(day, "P007")?.patient_id, "P005");
  assert.equal(nextPatient([appt("P004", "08:40", "done")], "P004"), null);
  assert.equal(nextPatient(day, "P001")?.patient_id, "P005"); // not on the day: the first left
});

test("which alerts still need an answer, by number", () => {
  assert.equal(stillToReview(["a", "b", "c", "d", "e"], new Set(["a", "d"])), "Alerts 2, 3 and 5 still need Accept or Override.");
  assert.equal(stillToReview(["a"], new Set()), "Alert 1 still needs Accept or Override.");
  assert.equal(stillToReview(["a"], new Set(["a"])), null);
});
