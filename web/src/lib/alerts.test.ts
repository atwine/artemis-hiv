import assert from "node:assert/strict";
import { test } from "node:test";

import { firstName, guidelineQuote, nextToReview, quotedPassage, severityWord, valueHeading } from "./alerts.ts";

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

test("the key sentence keeps the citation of the passage it came from", () => {
  const ext = {
    key_sentence: "If GFR is < 60mls/min then substitute with ABC.",
    references: ["Uganda HIV Guidelines 2022 · p. 260", "Uganda HIV Guidelines 2022 · p. 270"],
    passages: [
      passage("Uganda HIV Guidelines 2022 · p. 260", "Do creatinine every 12 months."),
      passage("Uganda HIV Guidelines 2022 · p. 270", "Do LFTs and RFTs. If GFR is < 60mls/min then substitute with ABC. More."),
    ],
  };
  const q = guidelineQuote(ext);
  assert.equal(q?.text, "If GFR is < 60mls/min then substitute with ABC.");
  assert.equal(q?.citation, "Uganda HIV Guidelines 2022 · p. 270");
  assert.equal(q?.whole, "Do LFTs and RFTs. If GFR is < 60mls/min then substitute with ABC. More.");
  assert.equal(q?.isKeySentence, true);
});

test("with no key sentence, the first passage the references name is quoted from its start", () => {
  const q = guidelineQuote({ key_sentence: null, references: ["Uganda HIV Guidelines 2022 · p. 9"], passages: [passage("Uganda HIV Guidelines 2022 · p. 9", "Start of the passage.")] });
  assert.equal(q?.text, "Start of the passage.");
  assert.equal(q?.isKeySentence, false);
  assert.equal(guidelineQuote({ key_sentence: null, references: [], passages: [] }), null);
});

test("a value's heading: the first name and 'today', or the date it was taken", () => {
  assert.equal(valueHeading("Rose Nabirye", "2026-02-24", "2026-02-24"), "Rose today");
  assert.equal(valueHeading("John Doe", "2024-10-01", "2026-01-22"), "John, 1 Oct 2024");
});

test("an AI alert that cited nothing quotes nothing, not even a key sentence from a passage it was shown", () => {
  const shown = passage("Uganda HIV Guidelines 2022 · p. 270", "If GFR is < 60mls/min then substitute with ABC.");
  const ext = { kind: "ai" as const, key_sentence: "If GFR is < 60mls/min then substitute with ABC.", references: [], passages: [shown] };
  assert.equal(guidelineQuote(ext), null);
  // A rule alert's key sentence still comes from the passages the search found.
  assert.equal(guidelineQuote({ ...ext, kind: "rule" as const })?.citation, "Uganda HIV Guidelines 2022 · p. 270");
});
