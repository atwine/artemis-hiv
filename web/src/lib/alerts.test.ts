import assert from "node:assert/strict";
import { test } from "node:test";

import { firstName, nextToReview, quotedPassage, severityWord } from "./alerts.ts";

const passage = (citation: string | null, text = "text") => ({ chunk_id: citation ?? "x", text, citation, metadata: {} });

test("the passage quoted is the first one the references name", () => {
  const p = quotedPassage({
    references: ["Uganda HIV Guidelines 2022 · p. 260", "Uganda HIV Guidelines 2022 · p. 270"],
    passages: [passage("Uganda HIV Guidelines 2022 · p. 270", "b"), passage("Uganda HIV Guidelines 2022 · p. 260", "a")],
  });
  assert.equal(p?.text, "a");
});

test("no passage is quoted when the references name none (the AI cited none, or no search)", () => {
  assert.equal(quotedPassage({ references: ["The AI cited no guideline passage for this alert."], passages: [passage("Uganda HIV Guidelines 2022 · p. 9")] }), null);
  assert.equal(quotedPassage({ references: [], passages: [] }), null);
});

test("severity words: the API's word, capitalised; none when the API sends none", () => {
  assert.equal(severityWord("high"), "High");
  assert.equal(severityWord("moderate"), "Moderate");
  assert.equal(severityWord(null), null);
  assert.equal(severityWord(""), null);
});

test("first name for the tray's question", () => {
  assert.equal(firstName("John Doe"), "John");
  assert.equal(firstName("  Amina  Nansubuga "), "Amina");
  assert.equal(firstName(""), "the patient");
});

test("the next alert to review comes after the current one, wrapping round; none when all are decided", () => {
  assert.equal(nextToReview(["a", "b", "c"], new Set(["a"]), 0), 1);
  assert.equal(nextToReview(["a", "b", "c"], new Set(["b", "c"]), 1), 0);
  assert.equal(nextToReview(["a", "b"], new Set(["a", "b"]), 0), null);
});
