import assert from "node:assert/strict";
import { test } from "node:test";

import { acceptDecision, overrideDecision } from "./decisions.ts";

test("accepting sends the API's Acknowledge with no reason", () => {
  assert.deepEqual(acceptDecision("a1"), { alert_id: "a1", action: "Acknowledge", comment: "" });
});

test("an override with a one-tap reason is ready at once", () => {
  assert.deepEqual(overrideDecision("a1", "Patient declined", ""), {
    alert_id: "a1",
    action: "Override",
    reason: "Patient declined",
    comment: "",
  });
});

test("'Other (say why)' is ready only with a comment, which is sent trimmed", () => {
  assert.equal(overrideDecision("a1", "Other (say why)", "   "), null);
  assert.deepEqual(overrideDecision("a1", "Other (say why)", "  private lab  "), {
    alert_id: "a1",
    action: "Override",
    reason: "Other (say why)",
    comment: "private lab",
  });
});
