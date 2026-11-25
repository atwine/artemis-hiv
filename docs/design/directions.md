# Five design directions (Phase 3, round 1)

The owner asked (2026-11-26) for five independent directions, not following any one pattern,
mixing ideas from the Design Library (Paper file "Design Library": pick two or three systems
and mix), with every workflow shown and new ideas for displaying the information. Each lives
on its own page of the Paper file **Artemis-HIV**. All five use `content-kit.md` and follow
`brief.md`. The owner picks, mixes or rejects after seeing them; nothing here is the chosen
direction.

## Screens every direction builds (same names, so they line up)

| Frame | What it shows |
|---|---|
| F0 · Cover + flow map | Name, the idea in one line, the library mix, palette and type swatches, a flow diagram of every stage with the buttons that move between them, new display ideas, what it gets and what it costs |
| S1 · Clinic list | Today's 7 patients with status, plus "Add patient case" |
| S2 · Visit before checks | Record and today's note for Rose Nabirye; "Run checks" |
| S3 · Checks running | Rules done, AI review in progress, what is being read |
| S4 · Results and review | RED, 5 alerts, 2 reviewed (one accepted, one overridden), the override reason picker shown, guideline text beside the patient values, Finalize locked |
| S5 · Plan comparison | AI plan vs the clinician's, item by item, regimen badge "Switch" |
| S6 · Finalize and visit record | The saved audit record after all five are reviewed, reopen, note-changed warning |
| S7 · Edge states | INCOMPLETE (David Mugisha) and GREEN (Amina Nansubuga) |
| S8 · Add patient case | Regimen pick-list with no "Select all", labs one row per result with unit |

Screens are 1366 x 768. Every status has a word and a shape, not only a colour. The brand
accent never uses the status reds, ambers or greens.

## 01 · Triage Board

- **Idea:** the clinic day is a queue; status colour is the organising signal. A
  keyboard-first, three-pane workstation: queue on the left, the visit in the middle, an alert
  rail on the right where each alert is reviewed in place.
- **Library mix:** Intercom (shared inbox, colour = status, Geist + Geist Mono) · Plane
  (states, approvals, keyboard hints) · Hex (quiet data tables).
- **Display ideas to explore:** a review ring on each queue row that fills as alerts are
  reviewed; a "left in red" count in the queue header; only a red alert pins itself to the top
  of the rail until it's decided (Penda: only red interrupts); key hints (A accept, O override,
  J/K next alert); lab table with change arrows and a tiny trend line.

## 02 · Guided Review

- **Idea:** one decision per screen, never scroll. A calm step-by-step path down a progress
  spine: Patient, Today's note, Checks, Alert 1 of 5 ... 5 of 5, Plan, Sign and save. Good for
  junior staff and for teaching.
- **Library mix:** Navattic (step tours, progress) · Sequence (calm white, pastel tints,
  Newsreader + Hanken Grotesk) · StackAI (mono labels, flow diagrams).
- **Display ideas to explore:** each alert screen split "In this patient's record" vs "What
  the Ugandan guideline says", with the matching numbers echoed in both; big Accept / Override
  buttons with reasons as large chips; each AI plan item has "Add to my plan", which writes it
  into the note; a final "Sign" screen that reads like a summary letter.

## 03 · Evidence Desk

- **Idea:** every claim is a pair: a patient fact and a guideline line, drawn connected. A
  reading desk where the guideline page sits open beside the record, the relevant row
  highlighted like a marker on paper.
- **Library mix:** GitBook (documentation layout, Hanken Grotesk, Geist Mono) · Steep
  (Newsreader serif, navy) · Wispr Flow (bookish serif for quoted guideline text).
- **Display ideas to explore:** numbered claims in the finding, each linked by a line to the
  exact value (creatinine 1.4) and the exact guideline sentence; a citation chip with document,
  edition, table and printed page plus "open the page"; an honest empty state for the
  ibuprofen alert, which has no Ugandan passage; "AI was shown 10 passages, cited 1".

## 04 · Patient Timeline

- **Idea:** problems live in time. The patient's story drawn as lanes from 2018 to today:
  regimen bars, other medicines, lab trends, notes. Alerts are flags pinned where the evidence
  is. The plan shows as two possible futures.
- **Library mix:** Cedar (stone, charcoal, spruce; Literata + Schibsted Grotesk) · Hex (quiet
  charts) · Attio (chips, two-tone titles).
- **Display ideas to explore:** guideline thresholds drawn on the chart (eGFR 60 dashed line,
  labelled with its citation); missed monitoring shaded as a gap ("no creatinine 2024 to
  2025"); regimen swimlanes (AZT/3TC/NVP 2018 to 2020, TDF/3TC/DTG 2020 to now); the plan
  comparison as two future lanes from today (the AI: ABC/3TC/DTG; the clinician: TDF continues)
  so the difference is visible at a glance; a review drawer that slides in from a flag.

## 05 · Note Co-pilot

- **Idea:** the clinician's note is the work; ARTEMIS reads it like a careful colleague and
  writes in the margin. Alerts anchor to the words they are about ("continue TLD" underlined,
  margin note beside it).
- **Library mix:** Superhuman (premium, stone, Inter, keyboard) · Wispr Flow (a serif note
  that reads like a document) · Intercom (colour = status).
- **Display ideas to explore:** margin notes anchored to text, Google-Docs-comment style, with
  Accept / Override on each; the AI plan as suggested edits (tracked changes: "continue TLD"
  struck through, "substitute TDF with ABC after a viral load" inserted), accepted or rejected
  one by one, which turns the item-by-item comparison into actions; alerts not tied to any
  words sit at the top of the margin; "Sign note" finalizes.
