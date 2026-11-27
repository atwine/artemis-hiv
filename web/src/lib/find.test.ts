import assert from "node:assert/strict";
import { test } from "node:test";

import type { DayAppointment } from "./day.ts";
import { findPatients, matchNote, type PatientSummary } from "./find.ts";

const patient = (patient_id: string, name: string): PatientSummary => ({
  patient_id, name, age_years: 30, sex: "F", art_regimen_current: ["TDF", "3TC", "DTG"], visit_date: "2026-11-26",
});
const PATIENTS = [patient("P003", "Sam Kato"), patient("P006", "Joan Nakato"), patient("Kintu-Test 001", "Sarah Nambi"), patient("P010", "")];

test("a name or an ID, any case, any part of it; nothing for an empty box", () => {
  assert.deepEqual(findPatients(PATIENTS, "kato").map((p) => p.patient_id), ["P003", "P006"]);
  assert.deepEqual(findPatients(PATIENTS, "  SA ").map((p) => p.patient_id), ["P003", "Kintu-Test 001"]);
  assert.deepEqual(findPatients(PATIENTS, "kintu").map((p) => p.patient_id), ["Kintu-Test 001"]);
  assert.deepEqual(findPatients(PATIENTS, "p01").map((p) => p.patient_id), ["P010"]);
  assert.deepEqual(findPatients(PATIENTS, " "), []);
});

test("at most eight matches, so the list stays short", () => {
  const many = Array.from({ length: 12 }, (_, i) => patient(`P1${i}`, `Patient ${i}`));
  assert.equal(findPatients(many, "patient").length, 8);
});

const appt = (patient_id: string, time: string): DayAppointment =>
  ({ patient_id, time, name: "", age_years: null, sex: "", regimen: "", state: "waiting", visit_id: null, status: null, ai_review: null, ai_review_label: null, ai_review_card_label: null, alert_count: 0, reviewed_count: 0, finalized_at: null }) as DayAppointment;

test("each match says when it is booked on the day shown, in today's words when that day is today", () => {
  const day = [appt("P003", "09:05")];
  assert.equal(matchNote("P003", day, "2026-11-27", "2026-11-27"), "today 09:05");
  assert.equal(matchNote("P006", day, "2026-11-27", "2026-11-27"), "not booked today");
  assert.equal(matchNote("P003", day, "2026-11-26", "2026-11-27"), "Thu 26 Nov 09:05");
  assert.equal(matchNote("P006", day, "2026-11-26", "2026-11-27"), "not booked Thu 26 Nov");
});
