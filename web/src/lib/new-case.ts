// Plain functions for adding a patient case (Paper FINAL S8a and S8b): the form's draft, its pick
// lists, what part 1 needs before part 2, the body POST /api/patients takes, and the draft kept
// in this browser while typing (owner, 2026-11-26). The backend checks everything again; these
// checks only save the doctor a round trip.
import type { components } from "./api/schema";

import { shortDay } from "./dates.ts";

type Schemas = components["schemas"];
export type NewCase = Schemas["NewCase"];
export type RegimenChoice = Schemas["RegimenChoice"];

export type Sex = "" | "F" | "M";
export type LabRow = { test: string; date: string; value: string; unit: string };
export type PastRegimen = { drugs: string[]; start: string; end: string };

/** The form as typed: every box is a string until it is sent. */
export type CaseDraft = {
  patientId: string;
  name: string;
  age: string;
  sex: Sex;
  visitDate: string; // YYYY-MM-DD
  time: string; // HH:MM, 24-hour
  visitType: string;
  drugs: string[]; // the current regimen, as single drugs
  medicines: string[]; // other medicines, one per line
  previousArt: PastRegimen[];
  labs: LabRow[];
  complaints: string;
  exam: string;
  history: string;
  note: string; // today's clinical notes
};

export type Part = 1 | 2;

/** What the browser keeps while the case is typed: which part is open, and the form. */
export type SavedDraft = { part: Part; draft: CaseDraft };

export function emptyDraft(today: string): CaseDraft {
  return {
    patientId: "",
    name: "",
    age: "",
    sex: "",
    visitDate: today,
    time: "",
    visitType: "",
    drugs: [],
    medicines: [],
    previousArt: [],
    labs: [],
    complaints: "",
    exam: "",
    history: "",
    note: "",
  };
}

/** The backend's list split as the design draws it: single drugs to tap, combinations as shortcuts. */
export function pickLists(regimens: RegimenChoice[]): { drugs: string[]; shortcuts: RegimenChoice[] } {
  return {
    drugs: regimens.filter((r) => r.drugs.length === 1).map((r) => r.choice),
    shortcuts: regimens.filter((r) => r.drugs.length > 1),
  };
}

export function toggleDrug(picked: string[], drug: string): string[] {
  return picked.includes(drug) ? picked.filter((d) => d !== drug) : [...picked, drug];
}

export function withShortcut(picked: string[], drugs: string[]): string[] {
  return [...picked, ...drugs.filter((d) => !picked.includes(d))];
}

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/; // the backend's own pattern for appointment_time

export function timeProblem(time: string): string | null {
  return TIME.test(time) ? null : "Give the appointment time as HH:MM, 24-hour (for example 09:30).";
}

/**
 * A medicine typed in the box but not added with "+ Add medicine": part 1 stops until the doctor
 * adds it or clears the box (owner, 2026-11-27), so nothing typed is dropped unseen.
 */
export function unaddedMedicine(box: string): string | null {
  const text = box.trim();
  return text ? `Press + Add medicine to keep '${text}', or clear the box.` : null;
}

export const blankPast = (a: PastRegimen) => !(a.drugs.length || a.start || a.end);

/** Previous ART as sent: rows left blank are dropped, so the backend's "row N" counts these. */
const pastSent = (d: CaseDraft) => d.previousArt.filter((a) => !blankPast(a));

/**
 * What part 1 still needs before the doctor moves on; the backend checks the rest on save. A
 * previous regimen without both dates can't be sent at all, so it is caught here, in the words
 * the backend uses for it.
 */
export function partOneProblems(d: CaseDraft): string[] {
  const problems: string[] = [];
  if (!d.patientId.trim()) problems.push("Patient ID is required."); // the backend's words for it
  const time = timeProblem(d.time);
  if (time) problems.push(time);
  pastSent(d).forEach((a, i) => {
    if (!(a.start && a.end)) problems.push(`Previous ART, row ${i + 1}: give a start and an end date.`);
  });
  return problems;
}

export const blankLab = (r: LabRow) => !(r.test || r.date.trim() || r.value.trim() || r.unit);

/** The body for POST /api/patients. */
export function toNewCase(d: CaseDraft): NewCase {
  const age = d.age.trim();
  return {
    patient_id: d.patientId.trim(),
    name: d.name.trim() || null,
    age_years: age ? Number(age) : null,
    sex: d.sex || null,
    visit_date: d.visitDate || null, // none: the backend books it today
    appointment_time: d.time,
    visit_type: (d.visitType || null) as NewCase["visit_type"],
    art_regimen: d.drugs,
    other_medications: d.medicines.map((m) => m.trim()).filter(Boolean),
    previous_art: pastSent(d).map((a) => ({ regimen: a.drugs, start_date: a.start, end_date: a.end })),
    labs: d.labs
      .filter((r) => !blankLab(r))
      .map((r) => ({
        test: r.test,
        date: r.date.trim(),
        value: r.value.trim(),
        unit: r.unit,
        when: r.date.trim() === d.visitDate ? ("today" as const) : ("previous" as const),
      })),
    complaints: d.complaints.trim(),
    examination_findings: d.exam.trim(),
    prior_history: d.history.trim(),
    todays_note: d.note,
  };
}

const NOT_ACCEPTED = "The case wasn't saved: a field isn't in the form the server expects. Check the boxes and try again.";

/**
 * Why the backend refused the case, one line per reason. Its own reasons (a string, or the
 * builder's list of strings) are shown as sent; a validation error's technical wording is not.
 */
export function formErrors(detail: unknown): string[] {
  if (typeof detail === "string") return [detail];
  if (Array.isArray(detail) && detail.length && detail.every((x) => typeof x === "string")) return detail;
  return [NOT_ACCEPTED];
}

/** The tray's line on part 2: "Adds Grace to today's clinic day." */
export function addsTo(name: string, visitDate: string, today: string): string {
  const who = name.trim().split(/\s+/)[0] || "the patient";
  if (!visitDate || visitDate === today) return `Adds ${who} to today's clinic day.`;
  return `Adds ${who} to the clinic day on ${shortDay(visitDate)}.`;
}

// The draft kept in this browser while typing. Made-up patients only for now: before any real
// patient is entered, this needs revisiting (docs/decisions.tsv, 2026-11-26).
export const DRAFT_KEY = "artemis.new-case-draft";

const TEXT_FIELDS = ["patientId", "name", "age", "sex", "visitDate", "time", "visitType", "complaints", "exam", "history", "note"] as const;
const FIELDS = new Set<string>([...TEXT_FIELDS, "drugs", "medicines", "previousArt", "labs"]);

const isText = (x: unknown): x is string => typeof x === "string";
const isTextList = (x: unknown): x is string[] => Array.isArray(x) && x.every(isText);
const isRecord = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null && !Array.isArray(x);

function isLab(x: unknown): x is LabRow {
  return isRecord(x) && isText(x.test) && isText(x.date) && isText(x.value) && isText(x.unit);
}

function isPast(x: unknown): x is PastRegimen {
  return isRecord(x) && isTextList(x.drugs) && isText(x.start) && isText(x.end);
}

function isDraft(x: unknown): x is CaseDraft {
  if (!isRecord(x) || Object.keys(x).some((k) => !FIELDS.has(k))) return false;
  return (
    TEXT_FIELDS.every((f) => isText(x[f])) &&
    ["", "F", "M"].includes(x.sex as string) &&
    isTextList(x.drugs) &&
    isTextList(x.medicines) &&
    Array.isArray(x.previousArt) &&
    x.previousArt.every(isPast) &&
    Array.isArray(x.labs) &&
    x.labs.every(isLab)
  );
}

/** A stored draft, or null when there is none or it isn't one (another version, or edited by hand). */
export function parseDraft(text: string | null): SavedDraft | null {
  if (!text) return null;
  let saved: unknown;
  try {
    saved = JSON.parse(text);
  } catch {
    return null;
  }
  if (!isRecord(saved) || (saved.part !== 1 && saved.part !== 2) || !isDraft(saved.draft)) return null;
  return { part: saved.part, draft: saved.draft };
}
