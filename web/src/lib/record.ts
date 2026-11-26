// Plain functions for the record panel of the visit screen (Paper FINAL S2, "From her record").
// Values and units are shown as recorded, never converted (owner, 2026-11-26).
import type { PatientDetail } from "./api/client";

import { longDate } from "./dates.ts";

type Labs = PatientDetail["labs"];
type LabResult = Labs[string][number];

/** Lab names as clinicians write them; anything else is the key in plain words. */
const LAB_NAMES: Record<string, string> = {
  egfr: "eGFR",
  cd4: "CD4",
  hb: "Haemoglobin",
  vl: "Viral load",
  alt: "ALT",
  ast: "AST",
  hba1c: "HbA1c",
  rbs: "RBS",
  fbs: "FBS",
  tb_lam: "TB LAM",
  crag: "CrAg",
};

export function labName(key: string): string {
  const k = key.trim().toLowerCase();
  if (LAB_NAMES[k]) return LAB_NAMES[k];
  const words = k.replace(/[_-]+/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}


function withUnit(r: LabResult): string {
  return r.unit.trim() ? `${r.value} ${r.unit.trim()}` : r.value;
}

/**
 * One row per test: its latest result ("today" when it is from today's visit), and its earliest
 * result for comparison when there is more than one, as the design shows "1.4 mg/dL today · 0.9 in 2020".
 */
export function labRows(labs: Labs, today: string): { label: string; text: string }[] {
  return Object.entries(labs)
    .filter(([, results]) => results.length > 0)
    .map(([key, results]) => {
      const byDate = [...results].sort((a, b) => a.date.localeCompare(b.date));
      const latest = byDate[byDate.length - 1];
      const earliest = byDate[0];
      const when = latest.date === today ? " today" : `, ${longDate(latest.date)}`;
      const before = byDate.length > 1 ? ` · ${withUnit(earliest)} in ${earliest.date.slice(0, 4)}` : "";
      return { label: labName(key), text: `${withUnit(latest)}${when}${before}` };
    });
}

export function labCount(labs: Labs): number {
  return Object.values(labs).reduce((n, results) => n + results.length, 0);
}

/** Regimens that ended, as "AZT/3TC/NVP, 2018–2020"; null when there are none. */
export function previousArt(history: PatientDetail["regimen_history"]): string | null {
  const ended = history
    .filter((h) => typeof h.end_date === "string" && h.end_date && Array.isArray(h.regimen))
    .map((h) => {
      const from = String(h.start_date ?? "").slice(0, 4);
      const to = String(h.end_date).slice(0, 4);
      return `${(h.regimen as unknown[]).map(String).join("/")}, ${from ? `${from}–${to}` : `until ${to}`}`;
    });
  return ended.length ? ended.join("; ") : null;
}

export function otherMedicines(meds: string[]): string | null {
  const list = meds.map((m) => m.trim()).filter(Boolean);
  return list.length ? list.join("; ") : null;
}

/** The patient line under a name: "P001 · 34 M · TDF/3TC/DTG". */
export function patientLine(p: Pick<PatientDetail, "patient_id" | "age_years" | "sex" | "art_regimen_current">): string {
  return [p.patient_id, `${p.age_years ?? "?"} ${p.sex}`.trim(), p.art_regimen_current.join("/")].filter(Boolean).join(" · ");
}

/** Whose record: "her", "his", or "the" when the sex isn't recorded as F or M. */
export function possessive(sex: string): string {
  const s = sex.trim().toUpperCase();
  return s === "F" ? "her" : s === "M" ? "his" : "the";
}

/** A sentence: a full stop added only when the text has no end mark. Punctuation only. */
export function asSentence(text: string): string {
  const t = text.trim();
  return /[.!?…]$/.test(t) ? t : `${t}.`;
}

/** Today's complaints and examination as the clinician wrote them; null when there are none. */
export function todaySummary(intake: PatientDetail["intake"]): string | null {
  const parts = [intake.complaints_symptoms, intake.examination_findings]
    .filter((v): v is string => typeof v === "string" && v.trim() !== "")
    .map(asSentence);
  return parts.length ? parts.join(" ") : null;
}

/**
 * What the checks read, from the record (S3): "Her regimen, 1 other medicine, 12 lab results,
 * today's notes, Ugandan guideline passages." The passages are the AI review's, when it runs.
 */
export function checkReads(
  p: Pick<PatientDetail, "sex" | "other_medications" | "labs" | "lab_notes">,
  aiReview: boolean,
): string {
  const meds = p.other_medications.filter((m) => m.trim()).length;
  const labs = labCount(p.labs);
  const parts = [
    `${possessive(p.sex)} regimen`,
    meds ? `${meds} other ${meds === 1 ? "medicine" : "medicines"}` : null,
    labs ? `${labs} lab ${labs === 1 ? "result" : "results"}` : null,
    p.lab_notes.length ? "lab notes" : null,
    "today's notes",
    aiReview ? "Ugandan guideline passages" : null,
  ].filter(Boolean) as string[];
  const text = parts.join(", ");
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}.`;
}

/**
 * What was checked (S7b), from the record: the regimen, every medicine (ARVs and others), lab
 * results, lab notes when there are any, and notes (earlier visits plus today's).
 */
export function checkedCounts(
  p: Pick<PatientDetail, "art_regimen_current" | "other_medications" | "labs" | "lab_notes" | "visits">,
  noteSent: string,
): { n: number; label: string }[] {
  const meds = p.art_regimen_current.length + p.other_medications.filter((m) => m.trim()).length;
  const notes = p.visits.length + (noteSent.trim() ? 1 : 0);
  const count = (n: number, one: string, many: string) => ({ n, label: n === 1 ? one : many });
  return [
    count(p.art_regimen_current.length ? 1 : 0, "regimen", "regimens"),
    count(meds, "medicine", "medicines"),
    count(labCount(p.labs), "lab result", "lab results"),
    ...(p.lab_notes.length ? [count(p.lab_notes.length, "lab note", "lab notes")] : []),
    count(notes, "note", "notes"),
  ];
}

/** [first sentence, the rest]: for a headline's bold part. Splits only; no words change. */
export function firstSentence(text: string): [string, string] {
  const m = /^([\s\S]*?[.!?])\s+([\s\S]+)$/.exec(text.trim());
  return m ? [m[1], m[2]] : [text.trim(), ""];
}
