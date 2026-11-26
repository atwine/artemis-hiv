// Plain functions for Finalize (S6a) and the saved visit record (S6b).
import type { DecisionOut, VisitCheck } from "./api/client";
import { clock } from "./dates.ts";
import type { DayAppointment } from "./day.ts";

/** "Accepted 09:47", or "Overridden 09:49 · Already done, not documented". */
export function decisionLine(d: DecisionOut): string {
  return d.action === "Acknowledge" ? `Accepted ${clock(d.saved_at)}` : `Overridden ${clock(d.saved_at)} · ${d.reason}`;
}

/** The patient to see next: the first not finalized after this one, else the first before it. */
export function nextPatient(day: DayAppointment[], currentId: string): DayAppointment | null {
  const open = day.filter((a) => a.state !== "done" && a.patient_id !== currentId);
  const current = day.find((a) => a.patient_id === currentId);
  if (!current) return open[0] ?? null;
  return open.find((a) => a.time > current.time) ?? open[0] ?? null;
}

/** "Alerts 2, 3 and 5 still need Accept or Override." (S6a); null when every alert has an answer. */
export function stillToReview(alertIds: string[], decided: Set<string>): string | null {
  const open = alertIds.map((id, i) => (decided.has(id) ? null : i + 1)).filter((n): n is number => n !== null);
  if (!open.length) return null;
  if (open.length === 1) return `Alert ${open[0]} still needs Accept or Override.`;
  return `Alerts ${open.slice(0, -1).join(", ")} and ${open[open.length - 1]} still need Accept or Override.`;
}

const AI_REVIEW_WORDS: Record<VisitCheck["ai_review"], string> = {
  ok: "Complete",
  not_run: "Switched off for this check",
  failed: "Failed: the model server did not answer",
  unreadable: "Failed: the reply could not be read",
  cut_off: "Incomplete: the reply was cut off",
  partly_read: "Incomplete: part of the reply could not be read",
  search_unavailable: "Not run: guideline search unavailable",
};

/** How the AI review ended, for the record (S6b's "AI review" row). */
export function aiReviewWords(outcome: VisitCheck["ai_review"]): string {
  return AI_REVIEW_WORDS[outcome];
}
