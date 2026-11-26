// The decisions sent to the backend, one alert at a time. The backend checks the same rules
// (artemis/review.py); checking here only keeps the Save button honest.
import type { DecisionIn } from "./api/client";

export type Reason = NonNullable<DecisionIn["reason"]>;

/** The reason that needs a comment (artemis/review.py, alert_resolution_ok). */
export const NEEDS_COMMENT: Reason = "Other (say why)";

/** "Accept alert" on screen is the API's "Acknowledge". */
export function acceptDecision(alertId: string): DecisionIn {
  return { alert_id: alertId, action: "Acknowledge", comment: "" };
}

/** An override, or null while "Other (say why)" has no comment yet. */
export function overrideDecision(alertId: string, reason: Reason, comment: string): DecisionIn | null {
  const text = comment.trim();
  if (reason === NEEDS_COMMENT && !text) return null;
  return { alert_id: alertId, action: "Override", reason, comment: text };
}
