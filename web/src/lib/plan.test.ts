import assert from "node:assert/strict";
import { test } from "node:test";

import { planState, verdictMark } from "./plan.ts";

test("each verdict the API sends gets the design's mark (S5); the others none, the words say it", () => {
  assert.equal(verdictMark("Matches your plan"), "●");
  assert.equal(verdictMark("Differs from your plan"), "≠");
  assert.equal(verdictMark("Partly in your plan"), "◐");
  assert.equal(verdictMark("Not in your plan"), "○");
  assert.equal(verdictMark("Not assessed"), null);
  assert.equal(verdictMark("No plan to compare"), null);
});

test("where Compare plans stands: one state from the saved plan and the latest request", () => {
  const made = { outcome: "made" as const, issues: [] as string[] };
  assert.equal(planState(null, "idle"), "none");
  assert.equal(planState(null, "pending"), "comparing");
  assert.equal(planState({ ...made }, "pending"), "comparing");
  assert.equal(planState(null, "error"), "refused");
  assert.equal(planState({ ...made, issues: ["missing_monitoring"] }, "error"), "refused"); // the refusal is the latest news
  assert.equal(planState({ outcome: "failed", issues: [] }, "idle"), "failed");
  assert.equal(planState({ ...made, issues: ["missing_monitoring"] }, "success"), "flagged");
  assert.equal(planState({ ...made }, "success"), "good");
  assert.equal(planState({ ...made }, "idle"), "good"); // a reopened visit's saved plan
});
