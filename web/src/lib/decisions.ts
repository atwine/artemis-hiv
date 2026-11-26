// The clinician's not-yet-saved choice on each alert, and what can be sent to the backend.
// The backend checks the same rules (artemis/review.py); checking here only keeps the Save
// button honest.
import type { DecisionIn } from "./api/client";

export type Action = DecisionIn["action"];
export type Reason = NonNullable<DecisionIn["reason"]>;

export type Draft = { action: Action; reason: Reason | null; comment: string };

/** The reason that needs a comment (artemis/review.py, alert_resolution_ok). */
const NEEDS_COMMENT: Reason = "Other";

export function draftReady(d: Draft): boolean {
  if (d.action === "Acknowledge") return true;
  if (d.reason === null) return false;
  return d.reason !== NEEDS_COMMENT || d.comment.trim() !== "";
}

/** The decisions to save, or null while any started one is incomplete or none is started. */
export function decisionsToSave(drafts: Record<string, Draft>): DecisionIn[] | null {
  const entries = Object.entries(drafts);
  if (entries.length === 0 || !entries.every(([, d]) => draftReady(d))) return null;
  return entries.map(([alert_id, d]) =>
    d.action === "Acknowledge"
      ? { alert_id, action: d.action, comment: "" }
      : { alert_id, action: d.action, reason: d.reason, comment: d.comment.trim() },
  );
}
