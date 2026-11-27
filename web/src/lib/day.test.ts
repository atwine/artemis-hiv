import assert from "node:assert/strict";
import { test } from "node:test";

import { clock, localDate, shortDay } from "./dates.ts";
import { appointmentNote, dayHeadline, dayHref, initials, nextForYou, type DayAppointment } from "./day.ts";

const appt = (over: Partial<DayAppointment>): DayAppointment => ({
  time: "09:30",
  patient_id: "P005",
  name: "Rose Nabirye",
  age_years: 38,
  sex: "F",
  regimen: "TDF/3TC/DTG",
  state: "waiting",
  visit_id: null,
  status: null,
  ai_review: null,
  ai_review_label: null,
  ai_review_card_label: null,
  alert_count: 0,
  reviewed_count: 0,
  finalized_at: null,
  ...over,
});

test("the headline: the day, then how many patients and how many need you, in words", () => {
  assert.deepEqual(dayHeadline("2026-11-26", 7, 1), ["Thursday 26 Nov.", "Seven patients, one waiting on you."]);
  assert.deepEqual(dayHeadline("2026-11-26", 1, 0), ["Thursday 26 Nov.", "One patient, none waiting on you."]);
  assert.deepEqual(dayHeadline("2026-11-26", 23, 2), ["Thursday 26 Nov.", "23 patients, two waiting on you."]);
});

test("a card's note: alerts reviewed, the API's card label, or when it was finalized", () => {
  assert.equal(appointmentNote(appt({ state: "needs_you", status: "RED", alert_count: 5, reviewed_count: 2 })), "2 of 5 alerts reviewed");
  assert.equal(appointmentNote(appt({ state: "needs_you", status: "INCOMPLETE", ai_review: "failed", ai_review_card_label: "AI review failed" })), "AI review failed");
  assert.equal(appointmentNote(appt({ state: "needs_you", status: "GREEN", ai_review: "ok" })), "No alerts");
  assert.match(appointmentNote(appt({ state: "done", status: "GREEN", finalized_at: "2026-11-26T06:52:00Z" })) ?? "", /^Finalized \d\d:\d\d$/);
  assert.equal(appointmentNote(appt({ state: "waiting" })), null);
});

test("the main button goes to the first visit that needs you", () => {
  const day = [appt({ time: "08:40", state: "done" }), appt({ time: "09:30", patient_id: "P005", state: "needs_you" }), appt({ time: "09:50", patient_id: "P006", state: "needs_you" })];
  assert.equal(nextForYou(day)?.patient_id, "P005");
  assert.equal(nextForYou([appt({})]), null);
});

test("clock time and initials", () => {
  assert.match(clock("2026-11-26T06:52:12.123456Z"), /^\d\d:\d\d$/);
  assert.equal(initials("Dr. A. Okello"), "AO");
  assert.equal(initials("Harriet Namubiru"), "HN");
});

test("a saved time's date, on this computer's calendar", () => {
  const iso = new Date(2026, 10, 26, 23, 30).toISOString(); // 23:30 local, maybe the next day in UTC
  assert.equal(localDate(iso), "26 Nov 2026");
});

test("a day's short name, for the links to the days around it", () => {
  assert.equal(shortDay("2026-11-24"), "Tue 24 Nov");
  assert.equal(shortDay("2026-11-27"), "Fri 27 Nov");
  assert.equal(shortDay("2099-01-05"), "Mon 5 Jan");
});

test("the board's address keeps the day and the view", () => {
  assert.equal(dayHref(null, false), "/");
  assert.equal(dayHref(null, true), "/?view=list");
  assert.equal(dayHref("2026-11-24", false), "/?date=2026-11-24");
  assert.equal(dayHref("2026-11-24", true), "/?date=2026-11-24&view=list");
});
