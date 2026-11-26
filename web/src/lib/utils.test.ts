// npm run test:unit (Node's own test runner; Node strips the types).
import assert from "node:assert/strict";
import { test } from "node:test";

import { cn } from "./utils.ts";

test("a design text size and a text colour both survive", () => {
  assert.equal(cn("text-13", "text-white"), "text-13 text-white");
  assert.equal(cn("text-15 leading-5", "text-tray-text"), "text-15 leading-5 text-tray-text");
});

test("a later design text size still replaces an earlier one", () => {
  assert.equal(cn("text-13", "text-20"), "text-20");
});

test("the design's radii and shadows merge like Tailwind's own", () => {
  assert.equal(cn("rounded-chip", "rounded-btn"), "rounded-btn");
  assert.equal(cn("shadow-window", "shadow-tray"), "shadow-tray");
});
