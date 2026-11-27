// "Find a patient" on the day screen (owner, 2026-11-27: "A, a find box"): any patient on record
// by name or ID, each with when they are booked on the day shown.
import type { components } from "./api/schema";

import { shortDay } from "./dates.ts";
import type { DayAppointment } from "./day.ts";

export type PatientSummary = components["schemas"]["PatientSummary"];

const MAX_MATCHES = 8;

/** Patients whose name or ID holds the words typed, in any case; none for an empty box. */
export function findPatients(patients: PatientSummary[], query: string): PatientSummary[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return patients.filter((p) => p.name.toLowerCase().includes(q) || p.patient_id.toLowerCase().includes(q)).slice(0, MAX_MATCHES);
}

/** "today 09:05", "not booked today"; for another day, that day's name: "Thu 26 Nov 09:05". */
export function matchNote(patientId: string, day: Pick<DayAppointment, "patient_id" | "time">[], dayDate: string, today: string): string {
  const when = dayDate === today ? "today" : shortDay(dayDate);
  const booked = day.find((a) => a.patient_id === patientId);
  return booked ? `${when} ${booked.time}` : `not booked ${when}`;
}
