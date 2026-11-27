// The management plan ("Compare plans", Paper FINAL S5) as the API sends it, and the little the
// screen adds to it.
import type { components } from "./api/schema";

export type ManagementPlan = components["schemas"]["ManagementPlan"];
export type PlanItem = components["schemas"]["PlanItem"];

/**
 * Where Compare plans stands for a visit:
 * - none: no plan asked for yet;
 * - comparing: the request is out;
 * - refused: the latest request was refused (429, 503, a network error);
 * - failed: no readable plan came back;
 * - flagged: a readable plan that failed the app's own checks;
 * - good: a readable plan that passed them.
 * A good plan is kept (pressing again shows it with no new AI call); the others can be tried again
 * (owner, 2026-11-27).
 */
export type PlanState = "none" | "comparing" | "refused" | "failed" | "flagged" | "good";

/** The latest request's state, as TanStack Query names it. */
export type RequestState = "idle" | "pending" | "error" | "success";

export function planState(plan: Pick<ManagementPlan, "outcome" | "issues"> | null, request: RequestState): PlanState {
  if (request === "pending") return "comparing";
  if (request === "error") return "refused";
  if (!plan) return "none";
  if (plan.outcome === "failed") return "failed";
  return plan.issues.length ? "flagged" : "good";
}

// The design's mark beside each verdict. "Not assessed" and "No plan to compare" have none: the
// words alone say it, and no mark should hint at agreement the AI never gave.
const MARKS: Record<string, string> = {
  "Matches your plan": "●",
  "Differs from your plan": "≠",
  "Partly in your plan": "◐",
  "Not in your plan": "○",
};

export function verdictMark(label: string): string | null {
  return MARKS[label] ?? null;
}
